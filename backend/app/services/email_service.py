"""Email delivery service using Resend API."""

import resend
from app.config import get_settings

settings = get_settings()


async def send_newsletter_email(
    to_email: str,
    subject: str,
    html_content: str,
) -> dict:
    """
    Send an HTML newsletter email via Resend.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_content: Full HTML content of the newsletter

    Returns:
        Resend API response dict with id and status
    """
    resend.api_key = settings.RESEND_API_KEY

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
