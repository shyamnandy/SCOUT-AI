"""Email delivery service using Resend API."""

import resend
from app.config import get_settings

settings = get_settings()


async def send_newsletter_email(
    to_email: str,
    subject: str,
    html_content: str,
    api_key: str | None = None,
) -> dict:
    """
    Send an HTML newsletter email via Resend.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_content: Full HTML content of the newsletter
        api_key: A user's own Resend key, if they've supplied one. Sending to
            themselves with their own key sidesteps Resend's sandbox-mode
            restriction (recipient must match the API key's account) without
            anyone needing to verify a domain. Falls back to the shared
            app-level key — that only reaches whatever address it's verified
            for.

    Returns:
        Resend API response dict with id and status
    """
    resend.api_key = api_key or settings.RESEND_API_KEY

    try:
        params = {
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        response = resend.Emails.send(params)
        return {"status": "sent", "id": response.get("id", ""), "error": None}
    except Exception as e:
        print(f"Email delivery failed to {to_email}: {e}")
        return {"status": "failed", "id": None, "error": str(e)}
