from sqlmodel import Session, select
from .schema import RegisterRequest
from ..database.user import User, UserSettings
from ..security.auth import hash_password
from ..database.security.queries import create_user_auth
from ..database.user.queries import get_user_settings, create_or_update_user_settings
from fastapi.exceptions import HTTPException
from uuid import UUID
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import json


class UserService:
    
    def register_user(self, session: Session, data: RegisterRequest) -> User:
        new_user = User(
            display_name=data.display_name or data.username
        )
        session.add(new_user)

        session.flush()

        try:
            create_user_auth(
                session=session,
                user_id=new_user.id,
                username=data.username,
                hashed_pass=hash_password(data.password)
            )
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=400, detail="Username already taken")

        session.commit()
        session.refresh(new_user)
        return new_user

    def get_user_by_id(self, session: Session, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id)
        return session.exec(statement).first()

    def get_user_or_404(self, session: Session, user_id: UUID) -> User:
        user = self.get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def get_users(self, session: Session, offset: int = 0, limit: int = 50) -> list[User]:
        statement = select(User).offset(offset).limit(limit)
        return list(session.exec(statement))

    def update_user(
        self,
        session: Session,
        user_id: UUID,
        display_name: str | None = None,
    ) -> User:
        user = self.get_user_or_404(session, user_id)

        if display_name is not None:
            user.display_name = display_name

        user.updated_at = datetime.utcnow()

        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    def update_user_partial(
        self,
        session: Session,
        user_id: UUID,
        data: dict
    ) -> User:
        user = self.get_user_or_404(session, user_id)

        for key, value in data.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()

        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    def delete_user(self, session: Session, user_id: UUID) -> bool:
        user = self.get_user_by_id(session, user_id)

        if not user:
            return False

        session.delete(user)
        session.commit()
        return True

    def get_user_settings(self, session: Session, user_id: UUID) -> dict:
        settings = get_user_settings(session, user_id)
        if not settings:
            return {}
        return json.loads(settings.settings)

    def save_user_settings(self, session: Session, user_id: UUID, settings: dict) -> dict:
        settings_json = json.dumps(settings)
        create_or_update_user_settings(session, user_id, settings_json)
        return settings