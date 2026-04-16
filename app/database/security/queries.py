from sqlmodel import Session, select
from uuid import UUID
from .schema import AuthUser
from ..user import User
from typing import Optional

def create_user_auth(session: Session,user_id: UUID, username: str, hashed_pass: str) -> User:
    """
    Handles the atomic creation of both the Profile and the Auth credentials.
    """

    
    # 2. Create Auth link
    new_auth = AuthUser(
        username=username,
        hashed_password=hashed_pass,
        user_id=user_id
    )
    session.add(new_auth)
    session.commit()

def get_auth_user_by_username(session: Session, username: str) -> Optional[AuthUser]:
    """Fetches credentials for login verification."""
    statement = select(AuthUser).where(AuthUser.username == username)
    return session.exec(statement).first()