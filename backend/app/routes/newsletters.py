"""Newsletter history API routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from app.schemas.newsletter import (
    NewsletterResponse, NewsletterListItem, ArticleSummary, UNSENT_STATUSES, RETENTION_HOURS,
)
from app.database import newsletters_collection, topics_collection
from app.utils import get_current_user
from bson import ObjectId

router = APIRouter(prefix="/api/newsletters", tags=["Newsletters"])


def _retention_cutoff() -> datetime:
    """Oldest send time still inside the retention window."""
    return datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)


def _display_status(nl: dict) -> str:
    """Collapse internal pipeline states into a single honest label —
    History shouldn't leak scheduler vocabulary ("draft") that reads like
    the newsletter was delivered when it wasn't."""
    status = nl.get("delivery_status", "unknown")
    return "unsent" if status in UNSENT_STATUSES else status


async def _topic_names(topic_ids: set[str]) -> dict[str, str]:
    """Batch topic-name lookup for a page of newsletters.

    Looking these up one `find_one` per newsletter (the original approach)
    meant a full extra MongoDB round-trip for every row in the list — up to
    `limit` (50) sequential awaits before the response could return. On a
    hosted DB that's easily several seconds just for History to load. One
    `$in` query fetches them all at once regardless of page size.
    """
    if not topic_ids:
        return {}
    cursor = topics_collection.find(
        {"_id": {"$in": [ObjectId(tid) for tid in topic_ids]}},
        {"name": 1},
    )
    return {str(doc["_id"]): doc["name"] async for doc in cursor}


@router.get("/", response_model=list[NewsletterListItem])
async def list_newsletters(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    topic_id: str | None = None,
    user: dict = Depends(get_current_user),
):
    """Get newsletter history for the current user, with optional topic filter.

    Includes drafts — curated content shows up here as soon as it's
    curated, not just once its delivery slot actually sends it.

    Only the last RETENTION_HOURS are served. The worker deletes past that
    age too; filtering here as well keeps History honest in the window
    between sweeps, and if the scheduler ever stops ticking.
    """
    query = {"user_id": user["id"], "delivered_at": {"$gte": _retention_cutoff()}}
    if topic_id:
        query["topic_id"] = topic_id

    # Aggregation rather than find(): $size collapses the articles array to
    # a count in the database, so the article bodies and rendered HTML never
    # cross the wire from Mongo at all, let alone reach the API response.
    cursor = newsletters_collection.aggregate([
        {"$match": query},
        {"$sort": {"delivered_at": -1}},
        {"$skip": skip},
        {"$limit": limit},
        {"$project": {
            "topic_id": 1,
            "title": 1,
            "delivered_at": 1,
            "delivery_status": 1,
            "article_count": {"$size": {"$ifNull": ["$articles", []]}},
        }},
    ])
    newsletters = await cursor.to_list(length=limit)

    names = await _topic_names({nl["topic_id"] for nl in newsletters})

    return [
        NewsletterListItem(
            id=str(nl["_id"]),
            topic_id=nl["topic_id"],
            topic_name=names.get(nl["topic_id"], "Deleted Topic"),
            title=nl["title"],
            article_count=nl["article_count"],
            delivered_at=nl["delivered_at"],
            delivery_status=_display_status(nl),
        )
        for nl in newsletters
    ]


@router.get("/{newsletter_id}", response_model=NewsletterResponse)
async def get_newsletter(
    newsletter_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific newsletter by ID, if it's still inside the retention
    window — an ID held open in a stale tab shouldn't resurrect content the
    listing has already stopped serving."""
    nl = await newsletters_collection.find_one({
        "_id": ObjectId(newsletter_id),
        "user_id": user["id"],
        "delivered_at": {"$gte": _retention_cutoff()},
    })
    if not nl:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    topic = await topics_collection.find_one({"_id": ObjectId(nl["topic_id"])}, {"name": 1})
    topic_name = topic["name"] if topic else "Deleted Topic"
    articles = nl.get("articles", [])

    return NewsletterResponse(
        id=str(nl["_id"]),
        topic_id=nl["topic_id"],
        topic_name=topic_name,
        title=nl["title"],
        article_count=len(articles),
        articles=[ArticleSummary(**a) for a in articles],
        # Prefer the combined HTML when this topic went out as part of a
        # batch — that's what actually landed in the inbox. html_content is
        # only this one topic's section.
        html_content=nl.get("batch_html") or nl.get("html_content", ""),
        delivered_at=nl["delivered_at"],
        delivery_status=_display_status(nl),
    )


@router.post("/trigger/{topic_id}")
async def trigger_newsletter(
    topic_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """
    Manually trigger newsletter generation for a specific topic.
    Runs in the background and returns immediately.
    """
    # Verify topic belongs to the user
    topic = await topics_collection.find_one({
        "_id": ObjectId(topic_id),
        "user_id": user["id"],
    })
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not topic.get("is_active", False):
        raise HTTPException(status_code=400, detail="Topic is inactive. Activate it first.")

    # Run in background so the API returns immediately
    background_tasks.add_task(_run_pipeline_for_topic, topic_id, user["id"])

    return {
        "message": f"Newsletter generation started for '{topic['name']}'",
        "topic_id": topic_id,
        "status": "generating",
    }


async def _run_pipeline_for_topic(topic_id: str, user_id: str):
    """
    Background task: curate and send one topic immediately.

    Uses the same pipeline as the scheduled worker so the two paths stay
    in sync; only the trigger and the slot bookkeeping differ.
    """
    from app.services.pipeline import curate_topic, build_draft_doc
    from app.services.email_service import send_newsletter_email
    from app.services.crypto_service import decrypt
    from app.database import users_collection
    from datetime import datetime, timezone

    try:
        topic = await topics_collection.find_one({"_id": ObjectId(topic_id)})
        user = await users_collection.find_one({"_id": ObjectId(user_id)})

        if not topic or not user:
            print(f"[Trigger] Topic or user not found: {topic_id}")
            return

        payload = await curate_topic(topic, user)
        if not payload:
            print(f"[Trigger] Nothing to send for topic {topic_id}")
            return

        # Manual sends aren't tied to a slot, so slot/local_date stay null.
        doc = build_draft_doc(topic, user, payload, slot=None, local_date=None)
        doc["delivery_status"] = "pending"
        nl_result = await newsletters_collection.insert_one(doc)

        print(f"[Trigger] Sending '{payload['topic_name']}' to {user['email']}")
        email_result = await send_newsletter_email(
            to_email=user["email"],
            subject=f"{payload['topic_name']} — Your ScoutAI Update",
            html_content=payload["html_content"],
            api_key=decrypt(user.get("resend_api_key")),
        )

        sent_at = datetime.now(timezone.utc)
        await newsletters_collection.update_one(
            {"_id": nl_result.inserted_id},
            {"$set": {"delivery_status": email_result["status"], "delivered_at": sent_at}},
        )
        if email_result["status"] == "sent":
            await topics_collection.update_one(
                {"_id": ObjectId(topic_id)},
                {"$set": {"last_delivered_at": sent_at}},
            )

        print(f"[Trigger] Done for '{payload['topic_name']}'")

    except Exception as e:
        print(f"[Trigger] Pipeline failed for topic {topic_id}: {e}")
