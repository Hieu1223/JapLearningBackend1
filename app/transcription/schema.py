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


class VideoProgressResponse(BaseModel):
    resource_id: str
    original_source: str
    current_page: int
    updated_at: datetime


class SaveVideoProgressRequest(BaseModel):
    resource_id: str
    original_source: str
    current_page: int