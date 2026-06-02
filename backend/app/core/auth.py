"""
JWT-based multi-tenancy primitives.

When MULTI_TENANCY_ENABLED=false (default):
  - /auth/login still issues a token for convenience
  - Other endpoints accept requests without a token (tenant_id = 'default')

When MULTI_TENANCY_ENABLED=true:
  - All data endpoints require a valid Bearer token
  - tenant_id is extracted from the JWT claim and used to filter retrieval

Demo user store
---------------
DEMO_USERS env var is a JSON dict of:
    { "username": { "password": "...", "tenant_id": "...", "role": "..." } }
Real production should replace this with a database + bcrypt hashes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import jwt as pyjwt

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TENANT_ID = "default"


# --------------------------------------------------------------------------- #
# Token operations
# --------------------------------------------------------------------------- #
def create_access_token(
    *, username: str, tenant_id: str, role: str = "engineer",
    settings: Optional[Settings] = None,
) -> Dict[str, object]:
    s = settings or get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=s.jwt_expiry_minutes)
    payload = {
        "sub": username,
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = pyjwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": exp.isoformat(),
        "tenant_id": tenant_id,
        "username": username,
        "role": role,
    }


def decode_token(token: str, settings: Optional[Settings] = None) -> Dict[str, object]:
    s = settings or get_settings()
    try:
        return pyjwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except pyjwt.ExpiredSignatureError:
        raise ValueError("token_expired")
    except pyjwt.InvalidTokenError as exc:
        raise ValueError(f"invalid_token: {exc}") from exc


# --------------------------------------------------------------------------- #
# Demo user verification
# --------------------------------------------------------------------------- #
def authenticate_user(
    username: str, password: str, settings: Optional[Settings] = None,
) -> Optional[Dict[str, str]]:
    """Return user record on success, None otherwise.

    NOTE: passwords are stored in plaintext in DEMO_USERS for capstone simplicity.
    In production, store bcrypt hashes and use passlib.hash.bcrypt.verify().
    """
    s = settings or get_settings()
    users = s.demo_users_dict
    record = users.get(username)
    if not record:
        return None
    if record.get("password") != password:
        return None
    return {
        "username": username,
        "tenant_id": record.get("tenant_id", DEFAULT_TENANT_ID),
        "role": record.get("role", "engineer"),
    }
