
from uuid import uuid4,UUID
from typing import Annotated,Dict,Any
from sqlmodel import Field, Session, SQLModel, create_engine, select
from fastapi import Depends
from datetime import datetime,timezone
from enum import Enum


class SupportedSite:
    Youtube = "Youtube"
    


class TranscriptStatus(Enum):
    Uploading = 0
    InQueue = 1
    Transcripting= 2
    Finish = 2


class Transcript(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: UUID = Field(primary_key=True, default_factory=lambda: uuid4)
    original_source : str = Field(default="File Upload")
    resource_id: str | None = Field(default=None)
    resource_url : str = Field()
    thumnail_url : str = Field()
    name : str = Field()
    date_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: str | None = Field(default=None)
    status : int = Field(default=TranscriptStatus.Uploading)
    public : bool