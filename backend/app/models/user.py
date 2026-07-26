"""User database model helpers."""

from datetime import datetime, timezone


def create_user_doc(email: str, name: str, password_hash: str) -> dict:
    """Create a new user document for MongoDB insertion."""
    return {
        "email": email,
        "name": name,
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc),
        "is_onboarded": False,
        # Delivery time slots the user has created on their dashboard.
        # Topics are dragged into these to be scheduled.
        "delivery_slots": ["08:00"],
        # When true, topics sharing a delivery slot go out as one combined
        # email instead of one email per topic.
        "batch_delivery": True,
        # Optional BYO API keys (Fernet-encrypted, see crypto_service).
        # None means "use the shared app-level key" for that service.
        "resend_api_key": None,
        "groq_api_key": None,
    }
