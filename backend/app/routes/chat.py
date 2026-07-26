"""Chat onboarding API routes."""

from fastapi import APIRouter, Depends, HTTPException
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse, ConfirmTopicResponse, FinishOnboardingRequest
from app.services.chat_service import chat_onboarding, extract_single_topic
from app.services.crypto_service import decrypt
from app.database import chat_sessions_collection, topics_collection, users_collection
from app.models.topic import create_topic_doc
from app.utils import get_current_user
from bson import ObjectId
from datetime import datetime, timezone

router = APIRouter(prefix="/api/chat", tags=["Chat Onboarding"])


@router.post("/onboarding", response_model=ChatMessageResponse)
async def send_onboarding_message(
    data: ChatMessageRequest,
    user: dict = Depends(get_current_user),
):
    """
    Send a message in the onboarding conversation.
    The AI responds conversationally and may extract topics when ready.
    """
    user_id = user["id"]

    # Get or create chat session
    session = await chat_sessions_collection.find_one({"user_id": user_id})

    if not session:
        session = {
            "user_id": user_id,
            "messages": [],
            "extracted_topics": [],
            "created_at": datetime.now(timezone.utc),
        }
        result = await chat_sessions_collection.insert_one(session)
        session["_id"] = result.inserted_id

    messages_history = session.get("messages", [])

    # Get AI response — the user's own Groq key if they've set one. A bad
    # key (typo, revoked, wrong type) surfaces as a provider auth error deep
    # in the LLM call; turn that into a clear pointer back to Profile rather
    # than a raw 500.
    try:
        result = await chat_onboarding(messages_history, data.message, decrypt(user.get("groq_api_key")))
    except Exception as exc:
        if user.get("groq_api_key"):
            raise HTTPException(
                status_code=502,
                detail="Your Groq API key was rejected. Double-check it in Profile — it may be invalid, revoked, or mistyped.",
            ) from exc
        raise

    # Update session with new messages
    new_messages = messages_history + [
        {"role": "user", "content": data.message},
        {"role": "assistant", "content": result["reply"]},
    ]

    await chat_sessions_collection.update_one(
        {"_id": session["_id"]},
        {"$set": {"messages": new_messages}},
    )

    return ChatMessageResponse(
        reply=result["reply"],
        awaiting_confirmation=result["awaiting_confirmation"],
    )


@router.post("/confirm", response_model=ConfirmTopicResponse)
async def confirm_topic(user: dict = Depends(get_current_user)):
    """
    Extract the structured topic from the current conversation on explicit
    user confirmation (button click), then reset the session so the next
    chat starts clean for a new topic.
    """
    session = await chat_sessions_collection.find_one({"user_id": user["id"]})
    if not session or not session.get("messages"):
        raise HTTPException(status_code=400, detail="No active conversation to confirm")

    try:
        topics = await extract_single_topic(session["messages"], decrypt(user.get("groq_api_key")))
    except Exception as exc:
        if user.get("groq_api_key"):
            raise HTTPException(
                status_code=502,
                detail="Your Groq API key was rejected. Double-check it in Profile — it may be invalid, revoked, or mistyped.",
            ) from exc
        raise
    await chat_sessions_collection.delete_one({"_id": session["_id"]})

    return ConfirmTopicResponse(topic=topics[0] if topics else None)


@router.post("/finish")
async def finish_onboarding(
    data: FinishOnboardingRequest,
    user: dict = Depends(get_current_user),
):
    """
    Finalize onboarding: create topics from the extracted/selected data
    and mark the user as onboarded.
    """
    user_id = user["id"]

    created_topics = []
    for topic in data.topics:
        expiration_date = (
            datetime.fromisoformat(topic.expiration_date) if topic.expiration_date else None
        )
        topic_doc = create_topic_doc(
            user_id=user_id,
            name=topic.name,
            keywords=topic.keywords,
            category=topic.category,
            description=topic.description,
            delivery_times=data.delivery_times,
            timezone_str=data.timezone,
            lifecycle=topic.suggested_lifecycle,
            expiration_date=expiration_date,
        )
        result = await topics_collection.insert_one(topic_doc)
        created_topics.append({
            "id": str(result.inserted_id),
            "name": topic.name,
        })

    # Mark user as onboarded
    await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_onboarded": True}},
    )

    return {"message": "Onboarding complete!", "topics_created": created_topics}


@router.delete("/session")
async def reset_chat_session(user: dict = Depends(get_current_user)):
    """Reset the chat session for re-onboarding."""
    await chat_sessions_collection.delete_many({"user_id": user["id"]})
    return {"message": "Chat session reset"}
