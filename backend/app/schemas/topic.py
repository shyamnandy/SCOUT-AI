"""Topic CRUD schemas."""

from pydantic import BaseModel
from datetime import datetime


class TopicCreateRequest(BaseModel):
    name: str
    keywords: list[str]
    category: str = "general"
    delivery_times: list[str] = ["08:00"]
    timezone: str = "Asia/Kolkata"
    lifecycle: str = "perpetual"
    expiration_date: datetime | None = None


class TopicUpdateRequest(BaseModel):
    name: str | None = None
    keywords: list[str] | None = None
    category: str | None = None
    delivery_times: list[str] | None = None
    timezone: str | None = None
    lifecycle: str | None = None
    expiration_date: datetime | None = None


class TopicResponse(BaseModel):
    id: str
    name: str
    keywords: list[str]
    category: str
    delivery_times: list[str]
    timezone: str
    lifecycle: str
    expiration_date: datetime | None
    is_active: bool
    created_at: datetime
    last_delivered_at: datetime | None
