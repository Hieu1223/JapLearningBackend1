from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from uuid import UUID
from typing import Annotated
from pydantic import BaseModel

from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    CurrentUser,
)
from ..database import SessionDep
from ..database.security.queries import get_auth_user_by_username, create_refresh_token as db_create_refresh_token, revoke_refresh_token
from ..database.user.queries import update_last_logged_in

router = APIRouter()


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RevokeTokenRequest(BaseModel):
    refresh_token: str


@router.post("/token", tags=["Security"], description="Authenticate a user with username and password and issue a new access/refresh token pair")
def login(
    session: SessionDep,
    form: OAuth2PasswordRequestForm = Depends()
) -> dict:
    auth_entry = get_auth_user_by_username(session, form.username)

    if not auth_entry or not verify_password(form.password, auth_entry.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    update_last_logged_in(session, auth_entry.user_id)

    access_token = create_access_token(auth_entry.user_id)
    refresh_token = db_create_refresh_token(session, auth_entry.user_id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token.token,
        "token_type": "bearer"
    }


@router.post("/token/refresh", tags=["Security"], description="Exchange a valid refresh token for a fresh access token")
def refresh_access_token(
    session: SessionDep,
    req: RefreshTokenRequest,
) -> dict:
    user_id = verify_refresh_token(session, req.refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    update_last_logged_in(session, user_id)

    access_token = create_access_token(user_id)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/token/revoke", tags=["Security"], description="Revoke a refresh token so it can no longer be used to obtain access tokens")
def revoke_token(
    session: SessionDep,
    req: RevokeTokenRequest,
    user_id: CurrentUser,
) -> dict:
    # Only the owner of the token may revoke it.
    token_owner = verify_refresh_token(session, req.refresh_token)
    if not token_owner:
        raise HTTPException(status_code=404, detail="Refresh token not found")
    if token_owner != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if not revoke_refresh_token(session, req.refresh_token):
        raise HTTPException(status_code=404, detail="Refresh token not found")
    return {"detail": "Token revoked successfully"}
