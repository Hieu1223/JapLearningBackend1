from ...database.transcription.schema import (
    SupportedSite,
    TranscriptStatus,
    TranscriptRequestResponse,
    TranscriptDetailResponse,
    VideoProgressResponse,
    TranscriptResult,
    TokenTimestamp,
)
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ── Submit job ─────────────────────────────────────────────────────────────────

class SubmitTranscriptionRequest(BaseModel):
    video_id: UUID


class TranscriptionJobResponse(BaseModel):
    transcript_id: UUID   # transcript row id
    success: bool


# ── List transcriptions ─────────────────────────────────────────────────────────

class TranscriptionListItem(BaseModel):
    transcript_id: UUID
    video_id: UUID
    original_source: str
    resource_id: Optional[str] = None
    name: str
    thumbnail_url: Optional[str] = None
    status: int
    done: bool
    msg: str


class TranscriptionListResponse(BaseModel):
    items: List[TranscriptionListItem]
    total: int


# ── Visited videos (derived from videoprogress) ─────────────────────────────────

class VisitedVideoResponse(BaseModel):
    video_id: UUID
    name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    original_source: Optional[str] = None
    resource_id: Optional[str] = None
    progress: float = 0.0
    updated_at: Optional[datetime] = None


class VisitedVideoListResponse(BaseModel):
    items: List[VisitedVideoResponse]
    total: int
