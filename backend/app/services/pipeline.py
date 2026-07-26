"""Shared newsletter pipeline.

Single implementation of search → scrape → filter → render, used by both
the Celery worker (scheduled deliveries) and the manual trigger route, so
the two paths can't drift apart.

These functions are storage-agnostic: they take plain dicts and return
plain dicts. Callers own the database writes.
"""

from datetime import datetime, timezone

from app.services.search_service import search_for_topic
from app.services.curator_service import (
    scrape_sources,
    filter_and_summarize,
    generate_newsletter,
)
from app.services.crypto_service import decrypt


async def curate_topic(topic: dict, user: dict) -> dict | None:
    """
    Run the full curation pipeline for one topic.

    Returns a payload ready to be stored as a newsletter draft, or None if
    no usable content could be produced.
    """
    topic_name = topic["name"]
    keywords = topic["keywords"]
    description = topic.get("description")
    category = topic.get("category")
    user_name = user["name"]
    # A user's own key, if they've set one — falls back to the shared
    # app-level key everywhere it's threaded through below.
    groq_api_key = decrypt(user.get("groq_api_key"))

    print(f"[curate] Searching: {topic_name}")
    sources = await search_for_topic(keywords, topic_name, description, category, groq_api_key)
    if not sources:
        print(f"[curate] No sources found for '{topic_name}'")
        return None

    print(f"[curate] Scraping {len(sources)} sources for '{topic_name}'")
    scraped = await scrape_sources(sources)

    print(f"[curate] Filtering and summarizing '{topic_name}'")
    articles = await filter_and_summarize(scraped, topic_name, keywords, description, groq_api_key)
    if not articles:
        print(f"[curate] Nothing relevant survived filtering for '{topic_name}'")
        return None

    print(f"[curate] Rendering newsletter for '{topic_name}'")
    html_content = await generate_newsletter(articles, topic_name, user_name, groq_api_key)

    return {
        "topic_name": topic_name,
        "title": f"{topic_name} — {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
        "articles": [a.model_dump() for a in articles],
        "html_content": html_content,
    }


def build_draft_doc(
    topic: dict,
    user: dict,
    payload: dict,
    slot: str | None,
    local_date: str | None,
) -> dict:
    """Shape a curation payload into a newsletter document."""
    now = datetime.now(timezone.utc)
    return {
        "user_id": str(topic["user_id"]),
        "topic_id": str(topic["_id"]),
        "topic_name": payload["topic_name"],
        "slot": slot,
        "local_date": local_date,
        "title": payload["title"],
        "articles": payload["articles"],
        "html_content": payload["html_content"],
        "delivery_status": "draft",
        "curated_at": now,
        # Overwritten with the real send time on dispatch; set now so
        # history sorting works for drafts that never ship.
        "delivered_at": now,
    }
