"""Content curation service — scrapes, analyzes, filters, and generates newsletters."""

import json
from langchain_community.document_loaders import WebBaseLoader
from app.config import get_settings, get_llm
from app.schemas.newsletter import ArticleSummary, NewsletterOutput
from jinja2 import Environment
from pathlib import Path

settings = get_settings()

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"

# Autoescape on: article titles and summaries come from scraped third-party
# pages, so they must never be rendered as raw HTML into the email.
_jinja_env = Environment(autoescape=True)


async def scrape_sources(sources: list[dict]) -> list[dict]:
    """
    Scrape full content from the selected source URLs.
    Falls back to the search snippet if scraping fails.
    """
    enriched = []

    for source in sources:
        url = source.get("url", "")
        full_content = source.get("content", "")

        if url:
            try:
                loader = WebBaseLoader(url)
                loader.requests_kwargs = {"timeout": 10}
                docs = loader.load()
                if docs and docs[0].page_content:
                    # Take first 3000 chars to stay within token limits
                    full_content = docs[0].page_content[:3000]
            except Exception as e:
                print(f"Scraping failed for {url}: {e}")
                # Keep the snippet from search as fallback

        enriched.append({
            "title": source.get("title", "Untitled"),
            "url": url,
            "content": full_content,
            "source_name": source.get("source_name", "Unknown"),
        })

    return enriched


async def filter_and_summarize(
    scraped_articles: list[dict],
    topic_name: str,
    keywords: list[str],
) -> list[ArticleSummary]:
    """
    AI-powered noise filtering and summarization:
    1. Score each article for relevance
    2. Discard irrelevant/low-quality articles
    3. Summarize the best ones into concise blurbs
    """
    llm = get_llm(temperature=0.3)

    articles_text = ""
    for i, article in enumerate(scraped_articles):
        content = article.get("content", "")[:2000]
        articles_text += f"""
--- ARTICLE {i+1} ---
Title: {article['title']}
Source: {article['source_name']}
URL: {article['url']}
Content: {content}
"""

    prompt = f"""You are an expert news curator. Analyze these articles for the topic "{topic_name}" (keywords: {', '.join(keywords)}).

{articles_text}

For each article, do the following:
1. SCORE its relevance to the topic (0.0 to 1.0)
2. DISCARD articles scoring below 0.5 (irrelevant, clickbait, or off-topic)
3. SUMMARIZE each remaining article in exactly 2-3 sentences — capture the key facts, not fluff
4. Extract the source name from the URL domain

Return a JSON array of objects with EXACTLY these fields:
- "title": the article title
- "summary": your 2-3 sentence summary
- "source_url": the article URL
- "source_name": the publisher name
- "relevance_score": your relevance score (0.0 to 1.0)

Sort by relevance_score descending. Return only the top 6 articles.
Return ONLY the JSON array, no other text."""

    response = await llm.ainvoke(prompt)

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        articles_data = json.loads(text)
        return [ArticleSummary(**a) for a in articles_data]
    except (json.JSONDecodeError, Exception) as e:
        print(f"Summarization parse error: {e}")
        # Fallback: return basic summaries
        return [
            ArticleSummary(
                title=a["title"],
                summary=a.get("content", "")[:200] + "...",
                source_url=a.get("url", ""),
                source_name=a.get("source_name", "Unknown"),
                relevance_score=0.7,
            )
            for a in scraped_articles[:6]
        ]


async def generate_newsletter(
    articles: list[ArticleSummary],
    topic_name: str,
    user_name: str,
) -> str:
    """
    Generate a beautiful HTML newsletter from the curated articles.
    Uses a Jinja2 template for the email layout.
    """
    llm = get_llm(temperature=0.5)

    # Generate a personalized greeting and closing
    articles_summary = "\n".join(
        f"- {a.title} ({a.source_name}): {a.summary}" for a in articles
    )

    prompt = f"""Write a brief, warm newsletter intro (1-2 sentences) and closing (1 sentence) for a personalized newsletter.

Topic: {topic_name}
Reader: {user_name}
Today's articles:
{articles_summary}

Return JSON with exactly: {{"greeting": "...", "closing": "..."}}
The greeting should reference the topic and sound personal. The closing should encourage the reader.
Return ONLY the JSON, no other text."""

    response = await llm.ainvoke(prompt)

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        meta = json.loads(text)
        greeting = meta.get("greeting", f"Here's your {topic_name} update!")
        closing = meta.get("closing", "Stay informed!")
    except Exception:
        greeting = f"Hey {user_name}! Here's your {topic_name} update for today."
        closing = "See you next time! — ScoutAI"

    # Render the HTML template
    template_path = TEMPLATE_DIR / "newsletter.html"
    try:
        template_content = template_path.read_text(encoding="utf-8")
        template = _jinja_env.from_string(template_content)
        html = template.render(
            topic_name=topic_name,
            greeting=greeting,
            articles=articles,
            closing=closing,
            user_name=user_name,
        )
    except Exception as e:
        print(f"Template render error: {e}")
        # Fallback to inline HTML
        html = _fallback_html(topic_name, greeting, articles, closing)

    return html


def render_batch_newsletter(sections: list[dict], user_name: str, slot_label: str) -> str:
    """
    Render several topics into a single combined newsletter.

    `sections` is a list of {"topic_name": str, "articles": [ArticleSummary-like dicts]}.
    Deterministic on purpose — no LLM call, to keep the per-delivery API
    budget at one curation pass per topic.
    """
    template_path = TEMPLATE_DIR / "newsletter_batch.html"
    try:
        template_content = template_path.read_text(encoding="utf-8")
        template = _jinja_env.from_string(template_content)
        return template.render(
            sections=sections,
            user_name=user_name,
            slot_label=slot_label,
            topic_count=len(sections),
        )
    except Exception as e:
        print(f"Batch template render error: {e}")
        parts = []
        for s in sections:
            parts.append(f"<h2>{s['topic_name']}</h2>")
            for a in s["articles"]:
                parts.append(
                    f"<p><strong>{a['title']}</strong><br>{a['summary']}<br>"
                    f"<a href=\"{a['source_url']}\">Read on {a['source_name']}</a></p>"
                )
        return (
            "<html><body style=\"font-family:Arial,sans-serif;padding:24px;\">"
            f"<h1>ScoutAI — {slot_label}</h1>{''.join(parts)}</body></html>"
        )


def _fallback_html(
    topic_name: str,
    greeting: str,
    articles: list[ArticleSummary],
    closing: str,
) -> str:
    """Fallback inline HTML if template fails."""
    articles_html = ""
    for a in articles:
        articles_html += f"""
        <div style="background:#1a1f35;border-radius:12px;padding:20px;margin-bottom:16px;border-left:4px solid #3b82f6;">
            <h3 style="color:#e2e8f0;margin:0 0 8px 0;font-size:16px;">{a.title}</h3>
            <p style="color:#94a3b8;margin:0 0 8px 0;font-size:14px;line-height:1.5;">{a.summary}</p>
            <a href="{a.source_url}" style="color:#3b82f6;font-size:13px;text-decoration:none;">Read on {a.source_name} →</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<body style="background:#0a0e1a;color:#e2e8f0;font-family:'Inter',Arial,sans-serif;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;">
        <h1 style="color:#3b82f6;font-size:24px;">📰 {topic_name}</h1>
        <p style="color:#94a3b8;font-size:15px;">{greeting}</p>
        {articles_html}
        <p style="color:#64748b;font-size:13px;margin-top:24px;text-align:center;">{closing}</p>
        <p style="color:#475569;font-size:11px;text-align:center;margin-top:16px;">Powered by ScoutAI</p>
    </div>
</body>
</html>"""
