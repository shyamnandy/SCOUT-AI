"""Authentication request/response schemas."""

from datetime import datetime
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_onboarded: bool
    created_at: datetime | None = None
    batch_delivery: bool = True


class PreferencesRequest(BaseModel):
    batch_delivery: bool
