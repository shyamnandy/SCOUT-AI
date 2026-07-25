"""Content curation service — scrapes, analyzes, filters, and generates newsletters."""

import base64
import json
from datetime import datetime, timezone
from functools import lru_cache
from html import escape

from langchain_community.document_loaders import WebBaseLoader
from app.config import get_settings, get_llm
from app.schemas.newsletter import ArticleSummary, NewsletterOutput
from jinja2 import Environment
from pathlib import Path

settings = get_settings()

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
LOGO_PATH = TEMPLATE_DIR / "assets" / "logo_email.png"

# Autoescape on: article titles and summaries come from scraped third-party
# pages, so they must never be rendered as raw HTML into the email.
_jinja_env = Environment(autoescape=True)


@lru_cache()
def _logo_data_uri() -> str | None:
    """
    Base64-embed the masthead logo so it renders with zero external
    dependency — no CDN/hosting needed, and it survives even when the
    recipient's client blocks remote images. Returns None (template just
    omits the <img>) until the asset file exists.
    """
    if not LOGO_PATH.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")


def _today_label() -> str:
    """'Saturday, July 25, 2026' — matches the masthead date style.

    Built without %-d/%#d (day-without-leading-zero): those flags are
    platform-specific — %-d on Linux/Mac, %#d on Windows — and using the
    wrong one raises ValueError, so the day is spliced in as a plain int.
    """
    now = datetime.now(timezone.utc)
    return f"{now:%A, %B} {now.day}, {now:%Y}"


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
            logo_src=_logo_data_uri(),
            today=_today_label(),
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
            logo_src=_logo_data_uri(),
            today=_today_label(),
        )
    except Exception as e:
        print(f"Batch template render error: {e}")
        # Same escaping requirement as _fallback_html: this bypasses Jinja's
        # autoescape, and article fields come from scraped third-party pages.
        parts = []
        for s in sections:
            parts.append(
                f'<p style="font-family:Georgia,serif;font-weight:700;font-size:17px;'
                f'color:#1c202b;border-bottom:2px solid #b9683f;display:inline-block;'
                f'padding-bottom:8px;">{escape(s["topic_name"])}</p>'
            )
            for a in s["articles"]:
                parts.append(
                    f'<div style="padding:0 4px 18px;margin-bottom:18px;border-bottom:1px solid rgba(28,32,43,0.1);">'
                    f'<h3 style="color:#1c202b;margin:0 0 8px;font-size:16px;font-family:Georgia,serif;">{escape(a["title"])}</h3>'
                    f'<p style="color:#64605a;margin:0 0 10px;font-size:14px;line-height:1.6;">{escape(a["summary"])}</p>'
                    f'<a href="{escape(a["source_url"])}" style="color:#7a4429;font-size:13px;font-weight:600;text-decoration:none;">'
                    f'Read on {escape(a["source_name"])} &rarr;</a></div>'
                )
        return (
            '<html><body style="background:#efebe1;color:#1c202b;font-family:Arial,sans-serif;padding:36px 20px;">'
            '<div style="max-width:600px;margin:0 auto;">'
            f'<h1 style="font-family:Georgia,serif;">ScoutAI — {escape(slot_label)}</h1>{"".join(parts)}'
            "</div></body></html>"
        )


def _fallback_html(
    topic_name: str,
    greeting: str,
    articles: list[ArticleSummary],
    closing: str,
) -> str:
    """
    Fallback inline HTML if the Jinja template fails to load/render.

    Article fields originate from scraped third-party pages, so every
    interpolated value is escape()'d here — this path has no Jinja
    autoescape to fall back on, and without it a crafted title/URL could
    break out of the markup.
    """
    articles_html = ""
    for a in articles:
        articles_html += f"""
        <div style="padding:0 4px 20px;margin-bottom:20px;border-bottom:1px solid rgba(28,32,43,0.1);">
            <p style="color:#7a4429;margin:0 0 8px;font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;">{escape(a.source_name)}</p>
            <h3 style="color:#1c202b;margin:0 0 9px;font-size:18px;font-family:Georgia,serif;">{escape(a.title)}</h3>
            <p style="color:#64605a;margin:0 0 11px;font-size:14.5px;line-height:1.6;">{escape(a.summary)}</p>
            <a href="{escape(a.source_url)}" style="color:#7a4429;font-size:13px;font-weight:600;text-decoration:none;border-bottom:1px solid rgba(122,68,41,0.35);">Continue reading &rarr;</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<body style="background:#efebe1;color:#1c202b;font-family:'Inter',Arial,sans-serif;padding:36px 20px;">
    <div style="max-width:600px;margin:0 auto;">
        <div style="background:#f6f3ec;border:1px solid rgba(28,32,43,0.12);border-radius:14px;padding:26px 24px;text-align:center;margin-bottom:28px;">
            <p style="font-family:Georgia,serif;font-weight:700;font-size:24px;color:#1c202b;margin:0;">ScoutAI<span style="color:#b9683f;">.</span></p>
            <p style="font-family:Georgia,serif;font-style:italic;font-size:13px;color:#9b9587;margin:8px 0 0;">{escape(topic_name)}</p>
        </div>
        <p style="color:#3d4250;font-size:15px;line-height:1.65;padding:0 4px;">{escape(greeting)}</p>
        {articles_html}
        <p style="font-family:Georgia,serif;font-style:italic;color:#3d4250;font-size:15px;margin-top:8px;text-align:center;padding-top:24px;border-top:1px solid rgba(28,32,43,0.12);">{escape(closing)}</p>
        <p style="color:#9b9587;font-size:11.5px;text-align:center;margin-top:20px;">Powered by ScoutAI</p>
    </div>
</body>
</html>"""
