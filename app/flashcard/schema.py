from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any

class Flashcard(BaseModel):
    id: UUID
    data: Optional[Dict[str, Any]] = None
    template_id: UUID

class UserFlashcard(BaseModel):
    id: UUID
    user_id: UUID
    flashcard_id: UUID
    created_at: datetime

class UserFlashcardSRS(BaseModel):
    id: UUID
    user_flashcard_id: UUID
    srs_data : Dict[str,Any]

class UserSchedulerData(BaseModel):
    id: UUID
    user_id: UUID
    data: Optional[Dict[str, Any]] = None


    