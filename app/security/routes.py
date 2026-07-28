from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from uuid import UUID
from typing import Annotated

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

router = APIRouter()

@router.post("/token")
def login(
    session: SessionDep,
    form: OAuth2PasswordRequestForm = Depends()
) -> dict:
    auth_entry = get_auth_user_by_username(session, form.username)
    
    if not auth_entry or not verify_password(form.password, auth_entry.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    access_token = create_access_token(auth_entry.user_id)
    refresh_token = db_create_refresh_token(session, auth_entry.user_id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token.token,
        "token_type": "bearer"
    }

@router.post("/token/refresh")
def refresh_access_token(
    session: SessionDep,
    refresh_token: str
) -> dict:
    user_id = verify_refresh_token(session, refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    access_token = create_access_token(user_id)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/token/revoke")
def revoke_token(
    session: SessionDep,
    refresh_token: str,
    user_id: CurrentUser
) -> dict:
    if not revoke_refresh_token(session, refresh_token):
        raise HTTPException(status_code=404, detail="Refresh token not found")
    return {"detail": "Token revoked successfully"}
