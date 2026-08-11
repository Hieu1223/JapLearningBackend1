from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional
from sqlmodel import SQLModel, Field


class TokenizationHistory(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    text: str = Field()
    sentences: int = Field(default=0)
    date_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
