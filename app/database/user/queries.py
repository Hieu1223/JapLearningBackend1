from sqlmodel import Session
from .schema import User, UserSettings


def create_user(session: Session, display_name: str | None = None) -> User:
    user = User(display_name=display_name)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

from sqlmodel import select
from uuid import UUID

def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    statement = select(User).where(User.id == user_id)
    return session.exec(statement).first()


def get_users(session: Session, offset: int = 0, limit: int = 50) -> list[User]:
    statement = select(User).offset(offset).limit(limit)
    return list(session.exec(statement))


from datetime import datetime


def update_user(
    session: Session,
    user_id: UUID,
    display_name: str | None = None,
) -> User | None:
    user = get_user_by_id(session, user_id)
    if not user:
        return None

    if display_name is not None:
        user.display_name = display_name

    user.updated_at = datetime.utcnow()

    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def delete_user(session: Session, user_id: UUID) -> bool:
    user = get_user_by_id(session, user_id)
    if not user:
        return False

    session.delete(user)
    session.commit()
    return True


# ── User Settings Queries ────────────────────────────────────────────────

def get_user_settings(session: Session, user_id: UUID) -> UserSettings | None:
    statement = select(UserSettings).where(UserSettings.user_id == user_id)
    return session.exec(statement).first()


def create_or_update_user_settings(
    session: Session,
    user_id: UUID,
    settings: str,
) -> UserSettings:
    settings_entry = get_user_settings(session, user_id)
    if not settings_entry:
        settings_entry = UserSettings(user_id=user_id, settings=settings)
        session.add(settings_entry)
    else:
        settings_entry.settings = settings
        settings_entry.updated_at = datetime.utcnow()
        session.add(settings_entry)
    session.commit()
    session.refresh(settings_entry)
    return settings_entry