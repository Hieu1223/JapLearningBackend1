from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    display_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_logged_in: Optional[datetime] = None


class UserSettings(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="user.id", unique=True)
    settings: str = Field(default="{}")
    updated_at: datetime = Field(default_factory=datetime.utcnow)