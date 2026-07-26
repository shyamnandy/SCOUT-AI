"""Chat message schemas."""

from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    message: str


class ExtractedTopic(BaseModel):
    name: str
    keywords: list[str]
    category: str
    description: str | None = None
    suggested_lifecycle: str = "perpetual"
    expiration_date: str | None = None


class ChatMessageResponse(BaseModel):
    reply: str
    awaiting_confirmation: bool = False


class ConfirmTopicResponse(BaseModel):
    topic: ExtractedTopic | None = None


class FinishOnboardingRequest(BaseModel):
    topics: list[ExtractedTopic]
    delivery_times: list[str] = ["08:00"]
    delivery_days: list[str] = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    timezone: str = "Asia/Kolkata"
