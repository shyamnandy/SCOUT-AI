"""Content curation service — scrapes, analyzes, filters, and generates newsletters."""

import asyncio
import json
from datetime import datetime, timezone
from html import escape

from langchain_community.document_loaders import WebBaseLoader
from app.config import get_settings, get_llm
from app.schemas.newsletter import ArticleSummary
from app.services.search_service import dedupe_by_event
from jinja2 import Environment
from pathlib import Path

settings = get_settings()

# How many articles ship in one topic's section. The floor is what a normal
# news day should produce; the ceiling only gets used when a topic genuinely
# has that much distinct news. Both are below the shortlist that feeds them,
# so same-story duplicates can be dropped without leaving gaps.
MIN_ARTICLE_COUNT = 5
MAX_ARTICLE_COUNT = 10
# Articles past the minimum have to earn the slot. Without this, a busy topic
# pads out to ten every time and the extra five are routine follow-ups that
# make the newsletter longer without making it more informative.
EXTRA_ARTICLE_IMPORTANCE_FLOOR = 0.6
# Below this relevance an article is dropped outright rather than counted
# toward the target — a thin section beats a padded one.
RELEVANCE_FLOOR = 0.4

# How many source pages to fetch at once. Bounded rather than unlimited: a
# shortlist can hold several articles from one outlet, and firing every
# request simultaneously is a good way to get rate-limited or blocked.
SCRAPE_CONCURRENCY = 6
SCRAPE_TIMEOUT_SECONDS = 10

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"

# Autoescape on: article titles and summaries come from scraped third-party
# pages, so they must never be rendered as raw HTML into the email.
_jinja_env = Environment(autoescape=True)


def _logo_src() -> str:
    """
    Absolute URL to the masthead logo, served by the deployed frontend.

    Gmail and Outlook both refuse to render `data:` URI <img> tags in email
    bodies, so the logo must be a real publicly-reachable URL instead of an
    inline base64 blob.
    """
    return f"{settings.FRONTEND_URL.rstrip('/')}/logo.png"


def _today_label() -> str:
    """'Saturday, July 25, 2026' — matches the masthead date style.

    Built without %-d/%#d (day-without-leading-zero): those flags are
    platform-specific — %-d on Linux/Mac, %#d on Windows — and using the
    wrong one raises ValueError, so the day is spliced in as a plain int.
    """
    now = datetime.now(timezone.utc)
    return f"{now:%A, %B} {now.day}, {now:%Y}"


def _load_url(url: str):
    """Blocking fetch of one page. Always called via a worker thread."""
    loader = WebBaseLoader(url)
    loader.requests_kwargs = {"timeout": SCRAPE_TIMEOUT_SECONDS}
    return loader.load()


async def _scrape_one(source: dict, semaphore: asyncio.Semaphore) -> dict:
    """Fetch one source's full text, falling back to its search snippet."""
    url = source.get("url", "")
    full_content = source.get("content", "")

    if url:
        async with semaphore:
            try:
                # WebBaseLoader.load() is synchronous — it uses `requests`
                # internally — so awaiting it directly is not an option and
                # calling it inline would block the event loop, freezing every
                # other request the API is serving for the duration of the
                # scrape. to_thread hands it to a worker thread instead.
                docs = await asyncio.to_thread(_load_url, url)
                if docs and docs[0].page_content:
                    # Take first 3000 chars to stay within token limits
                    full_content = docs[0].page_content[:3000]
            except Exception as e:
                print(f"Scraping failed for {url}: {e}")
                # Keep the snippet from search as fallback

    return {
        "title": source.get("title", "Untitled"),
        "url": url,
        "content": full_content,
        "source_name": source.get("source_name", "Unknown"),
    }


async def scrape_sources(sources: list[dict]) -> list[dict]:
    """
    Scrape full content from the selected source URLs, concurrently.

    Sequentially this is the slowest stage in the pipeline by a wide margin —
    a full shortlist of dead-slow hosts costs SHORTLIST_SIZE × the timeout —
    and it runs inside the cron tick, where that delay stalls every other
    topic due in the same slot.

    `gather` preserves input order, so the shortlist's importance ranking
    survives into the curation prompt.
    """
    semaphore = asyncio.Semaphore(SCRAPE_CONCURRENCY)
    return await asyncio.gather(*(_scrape_one(s, semaphore) for s in sources))


async def filter_and_summarize(
    scraped_articles: list[dict],
    topic_name: str,
    keywords: list[str],
    description: str | None = None,
    groq_api_key: str | None = None,
) -> list[ArticleSummary]:
    """
    Final curation pass over the scraped shortlist:
    1. Re-label which event each article covers, now that full text is available
    2. Score relevance and how important the story is
    3. Keep one article per event and summarize between MIN_ARTICLE_COUNT and
       MAX_ARTICLE_COUNT of them, depending on how much cleared the bar

    The event re-labeling matters here even though search already did it:
    search only saw short snippets, which routinely hide that two articles are
    the same story. Full text exposes those overlaps.
    """
    llm = get_llm(temperature=0.3, groq_api_key=groq_api_key)

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

    focus_line = f'\nUSER\'S SPECIFIC FOCUS: {description}' if description else ""

    prompt = f"""You are an expert news curator. Analyze these articles for the topic "{topic_name}" (keywords: {', '.join(keywords)}).{focus_line}

{articles_text}

For EVERY article above, return one object with EXACTLY these fields:
- "title": the article title
- "summary": a 2-3 sentence summary capturing the key facts, not fluff
- "source_url": the article URL
- "source_name": the publisher name from the URL domain
- "relevance_score": 0.0-1.0, how directly it matches the topic{" and the user's stated focus above" if description else ""}
- "importance": 0.0-1.0, how significant this development is for someone following this topic —
  major decisions, outcomes, and announcements rank high; routine follow-ups and commentary rank low
- "event_key": a short lowercase slug naming the SPECIFIC underlying news event reported
  (e.g. "education-minister-resignation", "cjp-verdict-appeal"). Articles about the SAME event MUST get
  the SAME slug even if they are from different outlets, are framed differently, or add small new details.
  Reaction pieces, follow-ups, and opinion columns about an event share that event's slug.

Rules:
- Include an entry for every article. Do NOT remove duplicates yourself — label them accurately and let
  the slugs repeat. Grouping happens after your response.
- Set relevance_score below 0.4 for anything off-topic, clickbait, or content-free; those get dropped.

Return ONLY the JSON array, no other text."""

    response = await llm.ainvoke(prompt)

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        scored = json.loads(text)
        if not isinstance(scored, list) or not scored:
            raise ValueError("empty or non-list curation payload")
    except (json.JSONDecodeError, ValueError, Exception) as e:
        print(f"Summarization parse error: {e}")
        # Fallback: basic summaries straight off the shortlist, which search
        # already reduced to one article per event.
        return [
            ArticleSummary(
                title=a["title"],
                summary=a.get("content", "")[:200] + "...",
                source_url=a.get("url", ""),
                source_name=a.get("source_name", "Unknown"),
                relevance_score=0.7,
            )
            for a in scraped_articles[:MIN_ARTICLE_COUNT]
        ]

    relevant = [a for a in scored if _read_score(a, "relevance_score") >= RELEVANCE_FLOOR]
    # One article per event, most important first. Distinctness is enforced
    # here in code, so a thin news day yields fewer articles rather than the
    # same story told several ways.
    distinct = dedupe_by_event(relevant, "importance")
    selected = _select_articles(distinct)

    print(
        f"[curate] '{topic_name}': {len(scored)} scored -> {len(relevant)} above floor -> "
        f"{len(distinct)} distinct events -> {len(selected)} delivered"
    )

    articles = []
    for a in selected:
        try:
            articles.append(ArticleSummary(**{
                "title": a["title"],
                "summary": a["summary"],
                "source_url": a.get("source_url", ""),
                "source_name": a.get("source_name", "Unknown"),
                "relevance_score": _read_score(a, "relevance_score"),
            }))
        except KeyError as e:
            print(f"Skipping malformed curated article, missing {e}")
    return articles


def _select_articles(distinct: list[dict]) -> list[dict]:
    """
    Take a variable number of articles depending on how much the topic earned.

    `distinct` arrives sorted by importance, descending. The first
    MIN_ARTICLE_COUNT are taken unconditionally — that's the promised size of
    an issue. Past that, each additional story is included only while it clears
    EXTRA_ARTICLE_IMPORTANCE_FLOOR, so a genuinely busy week can run to
    MAX_ARTICLE_COUNT while a quiet one still stops at the minimum.

    The loop breaks rather than filters: the input is sorted, so the first
    article that misses the bar guarantees none after it clears either.
    """
    selected = distinct[:MIN_ARTICLE_COUNT]
    for article in distinct[MIN_ARTICLE_COUNT:MAX_ARTICLE_COUNT]:
        if _read_score(article, "importance") < EXTRA_ARTICLE_IMPORTANCE_FLOOR:
            break
        selected.append(article)
    return selected


def _read_score(item: dict, field: str) -> float:
    """Read a numeric score off an LLM-produced dict, tolerating junk."""
    try:
        return float(item.get(field, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


async def generate_newsletter(
    articles: list[ArticleSummary],
    topic_name: str,
    user_name: str,
    groq_api_key: str | None = None,
) -> str:
    """
    Generate a beautiful HTML newsletter from the curated articles.
    Uses a Jinja2 template for the email layout.
    """
    llm = get_llm(temperature=0.5, groq_api_key=groq_api_key)

    # Generate a personalized closing line
    articles_summary = "\n".join(
        f"- {a.title} ({a.source_name}): {a.summary}" for a in articles
    )

    prompt = f"""Write a brief, warm one-sentence closing line for a personalized newsletter.

Topic: {topic_name}
Reader: {user_name}
Today's articles:
{articles_summary}

Return JSON with exactly: {{"closing": "..."}}
The closing should encourage the reader to keep following the topic.
Return ONLY the JSON, no other text."""

    response = await llm.ainvoke(prompt)

    try:
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        meta = json.loads(text)
        closing = meta.get("closing", "Stay informed!")
    except Exception:
        closing = "See you next time! — ScoutAI"

    # Render the HTML template
    template_path = TEMPLATE_DIR / "newsletter.html"
    try:
        template_content = template_path.read_text(encoding="utf-8")
        template = _jinja_env.from_string(template_content)
        html = template.render(
            topic_name=topic_name,
            articles=articles,
            closing=closing,
            user_name=user_name,
            logo_src=_logo_src(),
            today=_today_label(),
        )
    except Exception as e:
        print(f"Template render error: {e}")
        # Fallback to inline HTML
        html = _fallback_html(topic_name, articles, closing)

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
            logo_src=_logo_src(),
            today=_today_label(),
        )
    except Exception as e:
        print(f"Batch template render error: {e}")
        # Same escaping requirement as _fallback_html: this bypasses Jinja's
        # autoescape, and article fields come from scraped third-party pages.
        parts = []
        for s in sections:
            parts.append(
                f'<p style="font-family:Georgia,serif;font-weight:700;font-size:30px;'
                f'line-height:1.2;color:#1c202b;padding:0 4px 16px;margin:0 0 18px;'
                f'border-bottom:3px solid #b9683f;">'
                f'Your {escape(s["topic_name"])} Briefing</p>'
            )
            for a in s["articles"]:
                parts.append(
                    f'<div style="padding:0 4px 18px;margin-bottom:18px;border-bottom:1px solid rgba(28,32,43,0.1);">'
                    f'<h3 style="color:#1c202b;margin:0 0 8px;font-size:21px;font-family:Georgia,serif;">{escape(a["title"])}</h3>'
                    f'<p style="color:#3d4250;margin:0 0 10px;font-family:Georgia,\'Times New Roman\',serif;font-size:18px;line-height:1.7;">{escape(a["summary"])}</p>'
                    f'<a href="{escape(a["source_url"])}" style="color:#7a4429;font-size:13px;font-weight:600;text-decoration:none;">'
                    f'Read on {escape(a["source_name"])} &rarr;</a></div>'
                )
        return (
            '<html><head>'
            '<meta name="color-scheme" content="light only">'
            '<meta name="supported-color-schemes" content="light only">'
            '</head>'
            '<body style="background:#efebe1;color:#1c202b;font-family:Arial,sans-serif;margin:0;padding:0;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#efebe1">'
            '<tr><td align="center" bgcolor="#efebe1" style="padding:36px 20px;">'
            '<div style="max-width:600px;margin:0 auto;text-align:left;">'
            f'<h1 style="font-family:Georgia,serif;">ScoutAI — {escape(slot_label)}</h1>{"".join(parts)}'
            "</div></td></tr></table></body></html>"
        )


def _fallback_html(
    topic_name: str,
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
            <h3 style="color:#1c202b;margin:0 0 9px;font-size:23px;font-family:Georgia,serif;">{escape(a.title)}</h3>
            <p style="color:#3d4250;margin:0 0 11px;font-family:Georgia,'Times New Roman',serif;font-size:18px;line-height:1.7;">{escape(a.summary)}</p>
            <a href="{escape(a.source_url)}" style="color:#7a4429;font-size:13px;font-weight:600;text-decoration:none;border-bottom:1px solid rgba(122,68,41,0.35);">Continue reading &rarr;</a>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="color-scheme" content="light only">
    <meta name="supported-color-schemes" content="light only">
</head>
<body style="background:#efebe1;color:#1c202b;font-family:'Inter',Arial,sans-serif;margin:0;padding:0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#efebe1">
    <tr><td align="center" bgcolor="#efebe1" style="padding:36px 20px;">
    <div style="max-width:600px;margin:0 auto;text-align:left;">
        <div style="background:#f6f3ec;border:1px solid rgba(28,32,43,0.12);border-radius:14px;padding:26px 24px;text-align:center;margin-bottom:28px;">
            <p style="font-family:Georgia,serif;font-weight:700;font-size:24px;color:#1c202b;margin:0;">ScoutAI<span style="color:#b9683f;">.</span></p>
            <p style="font-family:Georgia,serif;font-style:italic;font-size:13px;color:#9b9587;margin:8px 0 0;">{escape(topic_name)}</p>
        </div>
        {articles_html}
        <p style="font-family:Georgia,serif;font-style:italic;color:#3d4250;font-size:15px;margin-top:8px;text-align:center;padding-top:24px;border-top:1px solid rgba(28,32,43,0.12);">{escape(closing)}</p>
        <p style="color:#9b9587;font-size:11.5px;text-align:center;margin-top:20px;">Powered by ScoutAI</p>
    </div>
    </td></tr>
    </table>
</body>
</html>"""
