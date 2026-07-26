"""Newsletter history API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from app.schemas.newsletter import NewsletterResponse, ArticleSummary
from app.database import newsletters_collection, topics_collection
from app.utils import get_current_user
from bson import ObjectId

router = APIRouter(prefix="/api/newsletters", tags=["Newsletters"])


def _nl_to_response(nl: dict, topic_name: str) -> NewsletterResponse:
    """Convert a MongoDB newsletter document to a NewsletterResponse."""
    return NewsletterResponse(
        id=str(nl["_id"]),
        topic_id=nl["topic_id"],
        topic_name=topic_name,
        title=nl["title"],
        articles=[ArticleSummary(**a) for a in nl.get("articles", [])],
        html_content=nl.get("html_content", ""),
        delivered_at=nl["delivered_at"],
        delivery_status=nl.get("delivery_status", "unknown"),
    )


@router.get("/", response_model=list[NewsletterResponse])
async def list_newsletters(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    topic_id: str | None = None,
    user: dict = Depends(get_current_user),
):
    """Get newsletter history for the current user, with optional topic filter."""
    # Drafts are pre-curated content awaiting their delivery slot — not history.
    query = {"user_id": user["id"], "delivery_status": {"$ne": "draft"}}
    if topic_id:
        query["topic_id"] = topic_id

    cursor = (
        newsletters_collection
        .find(query)
        .sort("delivered_at", -1)
        .skip(skip)
        .limit(limit)
    )
    newsletters = await cursor.to_list(length=limit)

    results = []
    for nl in newsletters:
        topic = await topics_collection.find_one({"_id": ObjectId(nl["topic_id"])})
        topic_name = topic["name"] if topic else "Deleted Topic"
        results.append(_nl_to_response(nl, topic_name))

    return results


@router.get("/{newsletter_id}", response_model=NewsletterResponse)
async def get_newsletter(
    newsletter_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a specific newsletter by ID."""
    nl = await newsletters_collection.find_one({
        "_id": ObjectId(newsletter_id),
        "user_id": user["id"],
    })
    if not nl:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    topic = await topics_collection.find_one({"_id": ObjectId(nl["topic_id"])})
    topic_name = topic["name"] if topic else "Deleted Topic"

    return _nl_to_response(nl, topic_name)


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
