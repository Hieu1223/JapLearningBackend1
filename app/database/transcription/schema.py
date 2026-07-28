from pydantic import BaseModel
from typing import Annotated
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from enum import Enum
from fastapi import UploadFile,File,Form


class SupportedSite:
    Youtube = "Youtube"
    FileUpload = "FileUpload"


class TranscriptStatus(Enum):
    Uploading = 0
    InQueue = 1
    Transcripting = 2
    Finish = 3
    Error = 4


# ── Database Models ───────────────────────────────────────────────────────────

class Transcript(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    original_source: str = Field(default=SupportedSite.FileUpload)
    resource_id: str | None = Field(default=None, index=True)
    resource_url: str = Field()
    thumnail_url: str = Field()
    name: str = Field()
    date_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: str | None = Field(default=None)
    status: int = Field(default=TranscriptStatus.Uploading.value, index=True)
    public: bool = Field(default=True)


class TranscriptionHistory(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id : UUID = Field(foreign_key="user.id") 
    transcript_id: UUID | None = Field(default=None, foreign_key="transcript.id", index=True)
    resource_id: str = Field(index=True)
    original_source: str = Field(default=SupportedSite.Youtube)
    name: str = Field()
    thumbnail_url: str = Field()
    resource_url: str = Field()
    date_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Request / Response schemas ────────────────────────────────────────────────

class YoutubeIDTranscriptRequestForm(BaseModel):
    resource_id : str

class YoutubeTranscriptRequestForm(BaseModel):
    name: str
    resource_id: str | None = None
    original_source: str = SupportedSite.Youtube
    public: bool = True
    thumbnail_url : str
    resource_url : str
    user_id: UUID
    


class TranscriptRequestResponse(BaseModel):
    transcript_id: UUID
    success: bool


class TranscriptStatusRequest(BaseModel):
    transcript_id : UUID


class TranscriptStatusResponse(BaseModel):
    done: bool
    msg: str

class TranscriptInfoRequest(BaseModel):
    transcript_id : UUID


class TranscriptInfoResponse(BaseModel):
    id: UUID
    original_source: str
    thumnail_url: str
    resource_url: str
    resource_id: str | None
    status: int


class TokenTimestamp(BaseModel):
    start: float | None
    end: float | None
    token: str

class TranscriptSegment(BaseModel):
    text : str
    words: list[TokenTimestamp]

class TranscriptResult(BaseModel):
    segments : list[TranscriptSegment]


class ErrorMessage(BaseModel):
    msg: str

# ── History Request / Response schemas ───────────────────────────────────────

class UserHistoryResponse(BaseModel):
    history_id: UUID
    transcript_id: UUID | None
    name: str
    thumbnail_url: str
    original_source: str
    date_created: datetime
    status: int | None = None
    is_transcribed: bool = False

class UserHistoryListResponse(BaseModel):
    items: list[UserHistoryResponse]
    total: int


class RemoveHistoryRequest(BaseModel):
    history_id: UUID


class TranscriptDetailResponse(BaseModel):
    id: UUID
    original_source: str
    thumnail_url: str
    resource_url: str
    resource_id: str | None
    status: int
    done: bool
    msg: str
    data: TranscriptResult | None = None