"""Web search service using Tavily to find legitimate news sources."""

from langchain_tavily import TavilySearch
from langchain_tavily.tavily_search import TavilySearchAPIWrapper
from app.config import get_settings, get_llm
from pydantic import BaseModel, Field

settings = get_settings()


class SourceSelection(BaseModel):
    """Structured output for selecting the 6 best sources."""
    sources: list[dict] = Field(
        description="List of 6 best source articles with title, url, content, and source_name"
    )


def get_search_tool():
    """Get the Tavily search tool configured for news.

    The key must go through TavilySearchAPIWrapper: TavilySearch itself has
    no `api_key` field and is configured with `extra="ignore"`, so passing
    one directly is silently dropped and the wrapper then falls back to a
    TAVILY_API_KEY environment variable that the Celery worker doesn't have.
    """
    if not settings.TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    return TavilySearch(
        max_results=15,
        topic="news",
        api_wrapper=TavilySearchAPIWrapper(tavily_api_key=settings.TAVILY_API_KEY),
    )


async def search_for_topic(
    keywords: list[str], topic_name: str, groq_api_key: str | None = None
) -> list[dict]:
    """
    Search the internet for a topic using Tavily, then use AI to select
    the 6 best legitimate sources.

    Args:
        keywords: List of search keywords for the topic
        topic_name: Human-readable topic name for context
        groq_api_key: A user's own Groq key, if they've supplied one.

    Returns:
        List of 6 best source articles with title, url, content, source_name
    """
    search_tool = get_search_tool()

    # Build an optimized search query from keywords
    search_query = f"latest news: {' '.join(keywords[:4])}"

    # Execute the search
    try:
        raw_results = search_tool.invoke({"query": search_query})
    except Exception as e:
        print(f"Tavily search error: {e}")
        return []

    # If results is a string (sometimes Tavily returns a summary string),
    # try a different approach
    if isinstance(raw_results, str):
        # Do a second search with different query formation
        try:
            alt_query = f"{topic_name} {keywords[0]} latest updates today"
            raw_results = search_tool.invoke({"query": alt_query})
        except Exception:
            return []

    # If still a string, parse it as best we can
    if isinstance(raw_results, str):
        return [{
            "title": topic_name,
            "url": "",
            "content": raw_results,
            "source_name": "Web Search",
        }]

    articles = _normalize_results(raw_results)

    # Use AI to select the 6 best, most legitimate sources
    if articles:
        return await select_best_sources(articles, topic_name, keywords, groq_api_key)

    print(f"Tavily returned no usable results for '{topic_name}'")
    return []


def _normalize_results(raw) -> list[dict]:
    """
    Coerce a Tavily response into a plain list of article dicts.

    TavilySearch returns a dict shaped like {"query": ..., "results": [...]},
    not a bare list, so callers must unwrap it before use.
    """
    if isinstance(raw, dict):
        results = raw.get("results", [])
        return results if isinstance(results, list) else []
    if isinstance(raw, list):
        return raw
    return []


async def select_best_sources(
    articles: list[dict],
    topic_name: str,
    keywords: list[str],
    groq_api_key: str | None = None,
) -> list[dict]:
    """
    Use AI to select the 6 most legitimate and relevant sources
    from the raw search results.
    """
    llm = get_llm(temperature=0.2, groq_api_key=groq_api_key)

    # Format articles for the LLM
    articles_text = ""
    for i, article in enumerate(articles):
        title = article.get("title", article.get("name", "Untitled"))
        url = article.get("url", article.get("link", ""))
        content = article.get("content", article.get("snippet", ""))[:500]
        articles_text += f"\n[{i+1}] Title: {title}\nURL: {url}\nContent: {content}\n"

    prompt = f"""You are a news editor selecting the 6 best, most legitimate sources for a topic.

TOPIC: {topic_name}
KEYWORDS: {', '.join(keywords)}

CANDIDATE ARTICLES:
{articles_text}

SELECT the 6 best articles based on:
1. LEGITIMACY — Prefer established news outlets (Reuters, BBC, TechCrunch, ESPN, etc.) over blogs or low-quality sites
2. RELEVANCE — Must be directly related to the topic and keywords
3. RECENCY — Prefer the most recent articles
4. DIVERSITY — Try to pick from different sources, not all from the same outlet
5. SUBSTANCE — Prefer articles with real information, not clickbait

If fewer than 6 legitimate articles exist, return only the legitimate ones.

Return a JSON array of objects, each with: title, url, content (the snippet), source_name (extracted from URL domain).
Return ONLY the JSON array, no other text."""

    response = await llm.ainvoke(prompt)

    # Parse the response
    import json
    try:
        # Try to extract JSON from the response
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        sources = json.loads(text)
        return sources[:6]
    except (json.JSONDecodeError, IndexError):
        # Fallback: return first 6 raw results
        return [
            {
                "title": a.get("title", a.get("name", "Untitled")),
                "url": a.get("url", a.get("link", "")),
                "content": a.get("content", a.get("snippet", "")),
                "source_name": _extract_domain(a.get("url", a.get("link", ""))),
            }
            for a in articles[:6]
        ]


def _extract_domain(url: str) -> str:
    """Extract a readable domain name from a URL."""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        domain = domain.replace("www.", "")
        return domain.split(".")[0].capitalize() if domain else "Unknown"
    except Exception:
        return "Unknown"
