"""Topic database model helpers."""

from datetime import datetime, timezone


def create_topic_doc(
    user_id: str,
    name: str,
    keywords: list[str],
    category: str,
    delivery_times: list[str],
    description: str | None = None,
    timezone_str: str = "Asia/Kolkata",
    lifecycle: str = "perpetual",
    expiration_date: datetime | None = None,
) -> dict:
    """Create a new topic document for MongoDB insertion."""
    # An ephemeral topic with no end date yet is created paused — the user
    # must set an end date (at creation or later from the dashboard) to activate it.
    is_active = not (lifecycle == "ephemeral" and expiration_date is None)
    return {
        "user_id": user_id,
        "name": name,
        "keywords": keywords,
        "category": category,
        "description": description,
        "delivery_times": delivery_times,
        "timezone": timezone_str,
        "lifecycle": lifecycle,
        "expiration_date": expiration_date,
        "is_active": is_active,
        "created_at": datetime.now(timezone.utc),
        "last_delivered_at": None,
    }
