"""Authentication API routes."""

from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse, PreferencesRequest,
)
from app.services.auth_service import hash_password, verify_password, create_access_token
from app.database import users_collection
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
    )
