"""
Authentication endpoints.

  POST /api/v1/auth/login   -> issue a JWT for a demo user
  GET  /api/v1/auth/me      -> introspect current principal (works without token)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.auth import authenticate_user, create_access_token
from app.core.config import Settings, get_settings
from app.core.security import get_current_principal
from app.models.schemas import LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Issue a JWT for a demo user (form-encoded)",
)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    user = authenticate_user(form.username, form.password, settings=settings)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        username=user["username"],
        tenant_id=user["tenant_id"],
        role=user["role"],
        settings=settings,
    )
    return LoginResponse(**token)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Introspect the current principal (helpful for the UI)",
)
async def me(principal: dict = Depends(get_current_principal)) -> MeResponse:
    return MeResponse(**principal)
