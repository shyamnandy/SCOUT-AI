"""Authentication API routes."""

from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse, PreferencesRequest, ApiKeysRequest,
    DeleteAccountRequest,
)
from app.services.auth_service import hash_password, verify_password, create_access_token
from app.services.crypto_service import encrypt
from app.database import users_collection, topics_collection, newsletters_collection, chat_sessions_collection
from app.models.user import create_user_doc
from app.utils import get_current_user
from bson import ObjectId

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest):
    """Register a new user account."""
    # Check if email already exists
    existing = await users_collection.find_one({"email": data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user document
    user_doc = create_user_doc(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
    )

    result = await users_collection.insert_one(user_doc)
    token = create_access_token(str(result.inserted_id))

    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    """Login with email and password."""
    user = await users_collection.find_one({"email": data.email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(str(user["_id"]))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        is_onboarded=user.get("is_onboarded", False),
        created_at=user.get("created_at"),
        batch_delivery=user.get("batch_delivery", True),
        has_resend_key=bool(user.get("resend_api_key")),
        has_groq_key=bool(user.get("groq_api_key")),
    )


@router.patch("/preferences", response_model=UserResponse)
async def update_preferences(
    data: PreferencesRequest,
    user: dict = Depends(get_current_user),
):
    """Update delivery preferences for the current user."""
    await users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"batch_delivery": data.batch_delivery}},
    )
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        is_onboarded=user.get("is_onboarded", False),
        created_at=user.get("created_at"),
        batch_delivery=data.batch_delivery,
        has_resend_key=bool(user.get("resend_api_key")),
        has_groq_key=bool(user.get("groq_api_key")),
    )


@router.patch("/api-keys", response_model=UserResponse)
async def update_api_keys(
    data: ApiKeysRequest,
    user: dict = Depends(get_current_user),
):
    """
    Save the caller's own Resend/Groq API keys, encrypted at rest.

    Sending an empty string for a field clears it (falls back to the
    shared app-level key); omitting a field leaves it untouched.
    """
    fields = data.model_dump(exclude_unset=True)
    update = {key: encrypt(value) for key, value in fields.items()}
    if update:
        await users_collection.update_one({"_id": ObjectId(user["id"])}, {"$set": update})

    fresh = await users_collection.find_one({"_id": ObjectId(user["id"])})
    return UserResponse(
        id=user["id"],
        email=fresh["email"],
        name=fresh["name"],
        is_onboarded=fresh.get("is_onboarded", False),
        created_at=fresh.get("created_at"),
        batch_delivery=fresh.get("batch_delivery", True),
        has_resend_key=bool(fresh.get("resend_api_key")),
        has_groq_key=bool(fresh.get("groq_api_key")),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    data: DeleteAccountRequest,
    user: dict = Depends(get_current_user),
):
    """
    Permanently delete the current user's account and every record scoped
    to it — topics, newsletter history, and any in-progress chat session.
    Nothing belonging to other users is touched.
    """
    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )

    user_id = user["id"]
    await topics_collection.delete_many({"user_id": user_id})
    await newsletters_collection.delete_many({"user_id": user_id})
    await chat_sessions_collection.delete_many({"user_id": user_id})
    await users_collection.delete_one({"_id": ObjectId(user_id)})
