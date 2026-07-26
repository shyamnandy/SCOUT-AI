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
    # Whether the user has their own key on file — never the key itself.
    has_resend_key: bool = False
    has_groq_key: bool = False


class PreferencesRequest(BaseModel):
    batch_delivery: bool


class ApiKeysRequest(BaseModel):
    # Omit a field to leave it unchanged; send "" to clear a previously-set key.
    resend_api_key: str | None = None
    groq_api_key: str | None = None
