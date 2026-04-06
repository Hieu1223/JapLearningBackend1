
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class UserProfile(BaseModel):
    id: UUID
    user_id: UUID
    display_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class TranscriptionHistory(BaseModel):
    id: UUID
    user_id: UUID
    transcription_id: UUID
    created_at: datetime

