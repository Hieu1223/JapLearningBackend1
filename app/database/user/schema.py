
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID,uuid4
from typing import Optional
from sqlmodel import SQLModel,Field


class User(SQLModel,table = True):
    __table_args__ = {"extend_existing": True}
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    display_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
