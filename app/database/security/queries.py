from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from uuid import UUID
from .schema import AuthUser, RefreshToken
from ..user import User
from typing import Optional
import secrets


def create_user_auth(session: Session, user_id: UUID, username: str, hashed_pass: str) -> User:
    new_auth = AuthUser(
        username=username,
        hashed_password=hashed_pass,
        user_id=user_id
    )
    session.add(new_auth)
    session.commit()

def get_auth_user_by_username(session: Session, username: str) -> Optional[AuthUser]:
    statement = select(AuthUser).where(AuthUser.username == username)
    return session.exec(statement).first()

def create_refresh_token(session: Session, user_id: UUID, expires_in_days: int = 7) -> RefreshToken:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    refresh_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    session.add(refresh_token)
    session.commit()
    session.refresh(refresh_token)
    return refresh_token

def get_refresh_token(session: Session, token: str) -> Optional[RefreshToken]:
    statement = select(RefreshToken).where(RefreshToken.token == token)
    return session.exec(statement).first()

def revoke_refresh_token(session: Session, token: str) -> bool:
    refresh_token = get_refresh_token(session, token)
    if not refresh_token:
        return False
    refresh_token.revoked = True
    session.add(refresh_token)
    session.commit()
    return True

def delete_expired_refresh_tokens(session: Session) -> int:
    now = datetime.now(timezone.utc)
    expired = session.exec(
        select(RefreshToken).where(RefreshToken.expires_at < now)
    ).all()
    for token in expired:
        session.delete(token)
    session.commit()
    return len(expired)