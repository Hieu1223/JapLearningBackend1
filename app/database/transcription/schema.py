from pydantic import BaseModel
from typing import Annotated, Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from enum import Enum
from fastapi import UploadFile, File, Form
from ...tokenization.schema import Token


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

class Video(SQLModel, table=True):
    __tablename__ = "video"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    original_source: str = Field(default=SupportedSite.FileUpload)
    resource_id: str | None = Field(default=None, index=True)
    resource_url: str = Field()
    thumbnail_url: str = Field()
    name: str = Field()
    date_created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: int = Field(default=TranscriptStatus.Uploading.value, index=True)
    public: bool = Field(default=True)
    individual_settings: str | None = Field(default=None)


class Transcript(SQLModel, table=True):
    __tablename__ = "transcript"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    video_id: UUID = Field(
        default=None,
        foreign_key="video.id",
        index=True,
        ondelete="CASCADE",
    )
    transcribed_by: UUID | None = Field(default=None, foreign_key="user.id")
    transcript_data: str | None = Field(default="{}")
    status: int = Field(default=TranscriptStatus.Uploading.value, index=True)
    transcript_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VideoProgress(SQLModel, table=True):
    __tablename__ = "videoprogress"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="user.id")
    video_id: UUID = Field(
        default=None,
        foreign_key="video.id",
        index=True,
        ondelete="CASCADE",
    )
    progress: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Request / Response schemas ────────────────────────────────────────────────

class YoutubeIDTranscriptRequestForm(BaseModel):
    resource_id: str


class YoutubeTranscriptRequestForm(BaseModel):
    name: str
    resource_id: str | None = None
    original_source: str = SupportedSite.Youtube
    public: bool = True
    thumbnail_url: str
    resource_url: str
    user_id: UUID


class TranscriptRequestResponse(BaseModel):
    transcript_id: UUID
    video_id: UUID
    success: bool


class TranscriptStatusRequest(BaseModel):
    transcript_id: UUID


class TranscriptStatusResponse(BaseModel):
    done: bool
    msg: str


class TranscriptInfoRequest(BaseModel):
    transcript_id: UUID


class TranscriptInfoResponse(BaseModel):
    id: UUID
    video_id: UUID | None
    original_source: str
    thumbnail_url: str
    resource_url: str
    resource_id: str | None
    name: str
    status: int


class TokenTimestamp(BaseModel):
    start: float | None
    end: float | None
    token: str


class TranscriptResult(BaseModel):
    # One list of GiNZA Tokens (with WhisperX timestamps) per transcript segment.
    segments: list[list[Token]]


class ErrorMessage(BaseModel):
    msg: str


# ── History Request / Response schemas ───────────────────────────────────────

class UserHistoryResponse(BaseModel):
    history_id: UUID
    video_id: UUID | None
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
    status: int
    done: bool
    msg: str
    data: TranscriptResult | None = None


class VideoProgressResponse(BaseModel):
    video_id: UUID
    progress: float
    updated_at: datetime


class SaveVideoProgressRequest(BaseModel):
    video_id: UUID
    progress: float


class SaveIndividualSettingsRequest(BaseModel):
    transcript_id: UUID
    settings: dict
