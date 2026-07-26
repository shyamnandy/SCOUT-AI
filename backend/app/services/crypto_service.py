"""Symmetric encryption for user-supplied secrets (BYO API keys).

Keys are derived from JWT_SECRET rather than a separate env var, so
deployments don't need one more secret to manage — rotating JWT_SECRET
does mean previously-encrypted keys become unreadable, same as it already
invalidates every issued token.
"""

import base64
import hashlib
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken
from app.config import get_settings


@lru_cache()
def _fernet() -> Fernet:
    settings = get_settings()
    digest = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str | None) -> str | None:
    """Encrypt a plaintext secret. Empty/None input clears the stored value."""
    if not value:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    """Decrypt a stored secret. Returns None for missing or unreadable values
    (e.g. JWT_SECRET rotated since it was encrypted) rather than raising —
    callers should fall back to the shared app-level key in that case."""
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return None
