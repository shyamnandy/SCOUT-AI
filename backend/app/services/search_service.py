"""Web search service using Tavily to find legitimate news sources."""

import json
import re

from langchain_tavily import TavilySearch
from langchain_tavily.tavily_search import TavilySearchAPIWrapper
from app.config import get_settings, get_llm

settings = get_settings()

# How many distinct-event sources to shortlist for scraping. Deliberately
# larger than the number of articles that ship, so the final curation stage
# has slack to drop same-story duplicates that only full text reveals and
# still fill the newsletter from genuinely different events. Must stay
# comfortably above curator_service.MAX_ARTICLE_COUNT, or a busy topic can
# never actually reach its ceiling.
SHORTLIST_SIZE = 16

# Reputable outlets to anchor the LLM's legitimacy judgment, grouped by
# category so a sports topic gets pointed at ESPN rather than Bloomberg.
CATEGORY_OUTLET_HINTS = {
    "technology": "TechCrunch, The Verge, Ars Technica, Wired, Reuters",
    "world_news": "Reuters, AP, BBC, The Guardian",
    "finance": "Bloomberg, Reuters, CNBC, Financial Times",
    "sports": "ESPN, BBC Sport, The Athletic",
    "entertainment": "Variety, The Hollywood Reporter, Billboard",
    "science": "Nature, Scientific American, Ars Technica",
}
DEFAULT_OUTLET_HINT = "Reuters, AP, BBC"


def get_search_tool(max_results: int = 20, tavily_api_key: str | None = None) -> TavilySearch:
    """Get the Tavily search tool configured for recent news.

    Args:
        tavily_api_key: A user's own Tavily key, if they've supplied one.
            Falls back to the shared app-level key everywhere it's threaded
            through below.

    The key must go through TavilySearchAPIWrapper: TavilySearch itself has
    no `api_key` field and is configured with `extra="ignore"`, so passing
    one directly is silently dropped and the wrapper then falls back to a
    TAVILY_API_KEY environment variable that the Celery worker doesn't have.
    """
    key = tavily_api_key or settings.TAVILY_API_KEY
    if not key:
        raise RuntimeError("No Tavily API key configured (set TAVILY_API_KEY or a per-user key)")

    return TavilySearch(
        max_results=max_results,
        topic="news",
        time_range="day",
        api_wrapper=TavilySearchAPIWrapper(tavily_api_key=key),
    )


def normalize_event_key(key: str) -> str:
    """
    Reduce an LLM-assigned event label to a comparable form.

    The model is asked for a short slug, but returns near-misses in practice
    ("CJP verdict" vs "cjp-verdict."), so keys are compared on alphanumeric
    words only rather than raw strings.
    """
    return " ".join(re.findall(r"[a-z0-9]+", (key or "").lower()))


def dedupe_by_event(items: list[dict], score_field: str) -> list[dict]:
    """
    Keep the single highest-scoring item per distinct event.

    Distinctness is enforced here rather than trusted to the prompt: the
    model reliably *labels* which story an article covers, but asking it to
    also drop duplicates competes with every other instruction in the
    prompt. Grouping in code makes it a guarantee.

    Items with no usable event key fall back to their URL, so an unlabeled
    article is treated as its own event instead of being silently dropped.
    """
    best: dict[str, dict] = {}
    for item in items:
        key = normalize_event_key(item.get("event_key", "")) or item.get("url") or item.get("source_url", "")
        if not key:
            continue
        current = best.get(key)
        if current is None or _score(item, score_field) > _score(current, score_field):
            best[key] = item
    return sorted(best.values(), key=lambda i: _score(i, score_field), reverse=True)


def _score(item: dict, field: str) -> float:
    """Read a numeric score off an LLM-produced dict, tolerating junk."""
    try:
        return float(item.get(field, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _build_queries(keywords: list[str], topic_name: str, description: str | None) -> list[str]:
    """
    Build several targeted queries instead of blending everything into one.

    A single query built from just the first few keywords misses whatever the
    rest of the keyword list covers, and ignores any stated intent entirely.
    Splitting keywords across queries and adding an intent-aware query widens
    the raw pool, which is what makes a genuinely distinct final set possible
    — you cannot pick 5 different stories out of a pool that only contains 2.
    """
    queries = []
    if keywords:
        queries.append(f"{topic_name}: {' '.join(keywords[:3])} latest news")
        if len(keywords) > 3:
            queries.append(f"{topic_name}: {' '.join(keywords[3:6])} latest news")
        if len(keywords) > 6:
            queries.append(f"{topic_name}: {' '.join(keywords[6:10])} latest news")
    if description:
        queries.append(f"{topic_name} — {description}")
    if not queries:
        queries.append(f"{topic_name} latest news")
    return queries[:3]


async def search_for_topic(
    keywords: list[str],
    topic_name: str,
    description: str | None = None,
    category: str | None = None,
    groq_api_key: str | None = None,
    tavily_api_key: str | None = None,
) -> list[dict]:
    """
    Search across several targeted queries, then shortlist the best source
    per distinct news event.

    Args:
        keywords: List of search keywords for the topic
        topic_name: Human-readable topic name for context
        description: Optional user-stated intent/focus for this topic
        category: Optional topic category, used to bias outlet legitimacy
        groq_api_key: A user's own Groq key, if they've supplied one.
        tavily_api_key: A user's own Tavily key, if they've supplied one.

    Returns:
        Up to SHORTLIST_SIZE articles, each covering a different event.
    """
    queries = _build_queries(keywords, topic_name, description)

    merged: dict[str, dict] = {}
    for query in queries:
        try:
            search_tool = get_search_tool(tavily_api_key=tavily_api_key)
            raw_results = search_tool.invoke({"query": query})
        except Exception as e:
            print(f"Tavily search error for query '{query}': {e}")
            continue

        for article in _normalize_results(raw_results):
            key = article.get("url") or article.get("link") or article.get("title", "")
            if key and key not in merged:
                merged[key] = article

    if not merged:
        # Fall back to the loosest possible query before giving up entirely.
        try:
            search_tool = get_search_tool(tavily_api_key=tavily_api_key)
            raw_results = search_tool.invoke({"query": f"{topic_name} latest updates today"})
            for article in _normalize_results(raw_results):
                key = article.get("url") or article.get("link") or article.get("title", "")
                if key:
                    merged[key] = article
        except Exception:
            pass

    if not merged:
        print(f"Tavily returned no usable results for '{topic_name}'")
        return []

    print(f"[search] '{topic_name}': {len(merged)} raw candidates from {len(queries)} queries")
    return await select_best_sources(
        list(merged.values()), topic_name, keywords, description, category, groq_api_key
    )


def _normalize_results(raw) -> list[dict]:
    """
    Coerce a Tavily response into a plain list of article dicts.

    TavilySearch returns a dict shaped like {"query": ..., "results": [...]},
    not a bare list, so callers must unwrap it before use. Occasionally it
    returns a bare summary string instead — nothing structured to extract,
    so that case is simply treated as no results.
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
    description: str | None = None,
    category: str | None = None,
    groq_api_key: str | None = None,
) -> list[dict]:
    """
    Label every candidate with the event it covers, then keep the single
    best-sourced article per event.

    The LLM's only jobs here are labeling and scoring; the actual
    one-article-per-event cut happens in `dedupe_by_event`.
    """
    llm = get_llm(temperature=0.2, groq_api_key=groq_api_key)

    articles_text = ""
    for i, article in enumerate(articles):
        title = article.get("title", article.get("name", "Untitled"))
        url = article.get("url", article.get("link", ""))
        content = article.get("content", article.get("snippet", ""))[:500]
        articles_text += f"\n[{i+1}] Title: {title}\nURL: {url}\nContent: {content}\n"

    outlet_hint = CATEGORY_OUTLET_HINTS.get(category, DEFAULT_OUTLET_HINT)
    focus_line = f"\nUSER'S SPECIFIC FOCUS: {description}" if description else ""

    prompt = f"""You are a news editor triaging today's coverage for a topic.

TOPIC: {topic_name}
KEYWORDS: {', '.join(keywords)}{focus_line}

CANDIDATE ARTICLES:
{articles_text}

For EVERY candidate above, return one object with these fields:
- "title": the article title
- "url": the article URL
- "content": the snippet text
- "source_name": publisher name from the URL domain
- "event_key": a short lowercase slug naming the SPECIFIC underlying news event this article reports
  (e.g. "education-minister-resignation", "cjp-verdict-appeal"). Articles reporting the SAME event MUST
  get the SAME slug, even when they come from different outlets or use different wording. This is the
  most important field — it is used to remove repeated coverage.
- "credibility": 0.0-1.0. Established outlets score higher (for this category: {outlet_hint}; other major
  outlets such as Reuters, AP, BBC also score well). Blogs, aggregators, and content farms score low.
- "relevance": 0.0-1.0 for how directly it matches the topic and keywords{" and the user's stated focus above" if description else ""}.

Rules:
- Include an entry for every candidate. Do NOT drop duplicates yourself — label them and let them repeat.
- Be strict about "same event": a follow-up, reaction piece, or opinion column about an event you already
  labeled shares that event's slug. Only genuinely separate developments get new slugs.

Return ONLY a JSON array, no other text."""

    response = await llm.ainvoke(prompt)

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        labeled = json.loads(text)
        if not isinstance(labeled, list) or not labeled:
            raise ValueError("empty or non-list selection payload")
    except (json.JSONDecodeError, IndexError, ValueError) as e:
        print(f"Source triage parse error: {e}")
        # Fall back to raw results, deduped by domain so at least the shortlist
        # isn't six articles from one outlet.
        seen_domains = set()
        fallback = []
        for a in articles:
            url = a.get("url", a.get("link", ""))
            domain = _extract_domain(url)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            fallback.append({
                "title": a.get("title", a.get("name", "Untitled")),
                "url": url,
                "content": a.get("content", a.get("snippet", "")),
                "source_name": domain,
            })
            if len(fallback) >= SHORTLIST_SIZE:
                break
        return fallback

    # One article per event, best-sourced first.
    distinct = dedupe_by_event(labeled, "credibility")
    shortlist = sorted(distinct, key=lambda a: _score(a, "relevance"), reverse=True)[:SHORTLIST_SIZE]
    print(
        f"[search] '{topic_name}': {len(labeled)} labeled -> "
        f"{len(distinct)} distinct events -> {len(shortlist)} shortlisted"
    )
    return shortlist


def _extract_domain(url: str) -> str:
    """Extract a readable domain name from a URL."""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        domain = domain.replace("www.", "")
        return domain.split(".")[0].capitalize() if domain else "Unknown"
    except Exception:
        return "Unknown"
