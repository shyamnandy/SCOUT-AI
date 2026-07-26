"""FastAPI dependency injection utilities."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import decode_access_token
from app.database import users_collection
from bson import ObjectId

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to extract and validate the current user from JWT token.
    Returns the full user document from MongoDB.
    """
    token = credentials.credentials
    user_id = decode_access_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    user["id"] = str(user["_id"])
    return user


def require_own_keys(user: dict):
    """Both a Groq and a Resend key are required before a topic can be created
    or chatted about — enforced server-side too since a frontend lock alone is
    trivially bypassable via direct API calls."""
    if not user.get("groq_api_key") or not user.get("resend_api_key"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Set your own Groq and Resend API keys in Profile before continuing.",
        )
