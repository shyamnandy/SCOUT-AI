"""Topic CRUD API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.topic import TopicCreateRequest, TopicUpdateRequest, TopicResponse
from app.database import topics_collection, users_collection
from app.models.topic import create_topic_doc
from app.utils import get_current_user, require_own_keys
from bson import ObjectId
from datetime import datetime, timezone

router = APIRouter(prefix="/api/topics", tags=["Topics"])


def _topic_to_response(doc: dict) -> TopicResponse:
    """Convert a MongoDB topic document to a TopicResponse."""
    return TopicResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        keywords=doc["keywords"],
        category=doc["category"],
        description=doc.get("description"),
        delivery_times=doc["delivery_times"],
        timezone=doc["timezone"],
        lifecycle=doc["lifecycle"],
        expiration_date=doc.get("expiration_date"),
        is_active=doc["is_active"],
        created_at=doc["created_at"],
        last_delivered_at=doc.get("last_delivered_at"),
    )


@router.get("/", response_model=list[TopicResponse])
async def list_topics(user: dict = Depends(get_current_user)):
    """Get all topics for the current user."""
    cursor = topics_collection.find({"user_id": user["id"]}).sort("created_at", -1)
    topics = await cursor.to_list(length=100)
    return [_topic_to_response(t) for t in topics]


@router.post("/", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    data: TopicCreateRequest,
    user: dict = Depends(get_current_user),
):
    """Create a new topic subscription."""
    require_own_keys(user)
    topic_doc = create_topic_doc(
        user_id=user["id"],
        name=data.name,
        keywords=data.keywords,
        category=data.category,
        description=data.description,
        delivery_times=data.delivery_times,
        timezone_str=data.timezone,
        lifecycle=data.lifecycle,
        expiration_date=data.expiration_date,
    )

    result = await topics_collection.insert_one(topic_doc)
    topic_doc["_id"] = result.inserted_id

    # Having a topic *is* what it means to be onboarded — flip the flag
    # here rather than relying on the user reaching a specific button/page,
    # so leaving the onboarding flow early (closed tab, browser back, a nav
    # click) never leaves a user with topics stuck being redirected back.
    if not user.get("is_onboarded"):
        await users_collection.update_one(
            {"_id": ObjectId(user["id"])},
            {"$set": {"is_onboarded": True}},
        )

    return _topic_to_response(topic_doc)


@router.put("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    data: TopicUpdateRequest,
    user: dict = Depends(get_current_user),
):
    """Update an existing topic."""
    topic = await topics_collection.find_one({
        "_id": ObjectId(topic_id),
        "user_id": user["id"],
    })
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Setting an end date on an ephemeral topic is what activates delivery.
    lifecycle = update_data.get("lifecycle", topic["lifecycle"])
    if update_data.get("expiration_date") and lifecycle == "ephemeral":
        update_data["is_active"] = True

    await topics_collection.update_one(
        {"_id": ObjectId(topic_id)},
        {"$set": update_data},
    )

    updated = await topics_collection.find_one({"_id": ObjectId(topic_id)})
    return _topic_to_response(updated)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a topic."""
    result = await topics_collection.delete_one({
        "_id": ObjectId(topic_id),
        "user_id": user["id"],
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Topic not found")


@router.patch("/{topic_id}/toggle", response_model=TopicResponse)
async def toggle_topic(
    topic_id: str,
    user: dict = Depends(get_current_user),
):
    """Toggle a topic between active and paused."""
    topic = await topics_collection.find_one({
        "_id": ObjectId(topic_id),
        "user_id": user["id"],
    })
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    new_status = not topic["is_active"]
    await topics_collection.update_one(
        {"_id": ObjectId(topic_id)},
        {"$set": {"is_active": new_status}},
    )

    topic["is_active"] = new_status
    return _topic_to_response(topic)
