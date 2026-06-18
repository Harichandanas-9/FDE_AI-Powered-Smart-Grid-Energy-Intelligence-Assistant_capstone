"""
FastAPI dependencies for resolving the current tenant.

Usage in a route:
    @router.get("/incidents")
    def list_incidents(tenant_id: str = Depends(get_current_tenant_id)):
        ...

Behavior matrix
---------------
                    MULTI_TENANCY_ENABLED=false   MULTI_TENANCY_ENABLED=true
    No token        -> "default"                  -> 401 Unauthorized
    Valid token     -> token.tenant_id            -> token.tenant_id
    Invalid token   -> "default" (ignored)        -> 401 Unauthorized
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.auth import DEFAULT_TENANT_ID, decode_token
from app.core.config import Settings, get_settings

# tokenUrl is the path where clients can obtain tokens; Swagger UI uses it
# to render the "Authorize" button correctly.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_principal(
    token: Optional[str] = Depends(_oauth2_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Resolve the calling principal: {username, tenant_id, role}.
    Falls back to a synthetic default principal when multi-tenancy is off
    and no token was supplied.
    """
    if not token:
        if settings.multi_tenancy_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing_bearer_token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"username": "anonymous", "tenant_id": DEFAULT_TENANT_ID, "role": "engineer"}

    try:
        payload = decode_token(token, settings=settings)
    except ValueError as exc:
        if settings.multi_tenancy_enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        return {"username": "anonymous", "tenant_id": DEFAULT_TENANT_ID, "role": "engineer"}

    return {
        "username": payload.get("sub", "unknown"),
        "tenant_id": payload.get("tenant_id", DEFAULT_TENANT_ID),
        "role": payload.get("role", "engineer"),
    }


def get_current_tenant_id(
    principal: dict = Depends(get_current_principal),
) -> str:
    """Extract only the ``tenant_id`` string from the resolved principal.

    Convenience dependency for routes that only need tenant isolation without
    the full principal dict.
    """
    return principal["tenant_id"]
