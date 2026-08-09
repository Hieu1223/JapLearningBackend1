from pydantic import BaseModel
from typing import Annotated, Optional
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


class VideoDetail(BaseModel):
    id: str
    title: str
    thumbnail_url: Optional[str]
    channel: Optional[str] = None
    duration: Optional[float] = None

    @staticmethod
    def from_dict(data: dict) -> "VideoDetail":
        channel = data.get("channel", {})
        channel_name = None
        if isinstance(channel, dict):
            channel_name = channel.get("name")
        elif isinstance(channel, str):
            channel_name = channel

        thumbnails = data.get("thumbnails") or []
        thumbnail_url = None
        if thumbnails:
            thumbnail_url = thumbnails[-1].get("url") if isinstance(thumbnails[-1], dict) else None

        return VideoDetail(
            id=data.get("id"),
            title=data.get("title"),
            thumbnail_url=thumbnail_url or data.get("thumbnail"),
            channel=channel_name,
            duration=data.get("duration"),
        )


class TranscriptDetailResponse(BaseModel):
    id: UUID
    original_source: str
    thumnail_url: str
    resource_url: str
    resource_id: str | None
    status: int
    done: bool
    msg: str
    video: VideoDetail | None = None
    data: TranscriptResult | None = None
    individual_settings: dict | None = None


class VideoProgressResponse(BaseModel):
    resource_id: str
    original_source: str
    current_page: int
    updated_at: datetime


class SaveVideoProgressRequest(BaseModel):
    resource_id: str
    original_source: str
    current_page: int


class SaveIndividualSettingsRequest(BaseModel):
    transcript_id: UUID
    settings: dict