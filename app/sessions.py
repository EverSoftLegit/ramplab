"""Session tokens (RAMP-019): weak vs. integrity-protected.

- Vulnerable: the token is just the base64 of the username, so anyone can forge
  a token for any account.
- Secure: the token is `owner.hmac(owner)`; a forged token fails verification
  because the attacker cannot produce the HMAC without the server secret.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

from app.config import WEBHOOK_SECRET

_SECRET = ("session:" + WEBHOOK_SECRET).encode()


def issue_weak_token(owner: str) -> str:
    return base64.urlsafe_b64encode(owner.encode()).decode()


def read_weak_token(token: str) -> str:
    """No integrity: whatever username the token decodes to is trusted."""
    try:
        return base64.urlsafe_b64decode(token.encode()).decode()
    except Exception:
        raise ValueError("Malformed token")


def issue_signed_token(owner: str) -> str:
    sig = hmac.new(_SECRET, owner.encode(), hashlib.sha256).hexdigest()
    return f"{owner}.{sig}"


def read_signed_token(token: str) -> str:
    """Verifies the HMAC before trusting the identity; forged tokens are rejected."""
    if "." not in token:
        raise ValueError("Malformed token")
    owner, _, sig = token.partition(".")
    expected = hmac.new(_SECRET, owner.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid token signature")
    return owner
