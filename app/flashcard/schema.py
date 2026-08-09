"""
flashcard/schema.py  (API layer — Pydantic models)
"""

from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal, List
from enum import Enum
from ..database.flashcard.schema import CardType


class CardState(str, Enum):
    NEW        = "new"
    LEARNING   = "learning"
    REVIEW     = "review"
    RELEARNING = "relearning"

class UserFlashcardSRS(BaseModel):
    id: UUID
    user_flashcard_id: UUID
    srs_data: str


class UserSchedulerData(BaseModel):
    id: UUID
    data: str


class AddVocabRequest(BaseModel):
    word: str = Field(..., min_length=1, description="The vocabulary word (e.g. the Japanese term)")
    meaning: str = Field(..., min_length=1, description="The meaning of the word (e.g. Vietnamese/English definition)")


class SaveReviewRequest(BaseModel):
    """Payload from the frontend ts-fsrs scheduler.

    ``card`` is the full ts-fsrs ``Card`` object (dates as ISO strings or
    epoch-ms). The backend persists its fields into the fsrs-native SrsCard.
    """
    card: dict


class DeckResponse(BaseModel):
    id:       UUID
    name:     str
    owner_id: UUID
    public:   bool

    model_config = ConfigDict(from_attributes=True)


class DeckStatsResponse(BaseModel):
    new:        int = 0
    learning:   int = 0
    due:        int = 0


class DeckWithStatsResponse(BaseModel):
    id:       UUID
    name:     str
    owner_id: UUID
    public:   bool
    stats:    DeckStatsResponse

    model_config = ConfigDict(from_attributes=True)


class DeckProgressResponse(BaseModel):
    total:      int
    new:        int
    learning:   int
    due:        int


class PublicDeckResponse(BaseModel):
    id:         UUID
    name:       str
    owner_id:   UUID
    card_count: int

    model_config = ConfigDict(from_attributes=True)


class CardResponse(BaseModel):
    id:         UUID
    deck_id:    UUID
    data:       str
    card_type:  CardType
    state:      CardState
    step:       Optional[int]   = None
    stability:  Optional[float] = None
    difficulty: Optional[float] = None
    due:        Optional[datetime] = None
    last_review: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CardWithSrsResponse(BaseModel):
    id:           UUID
    deck_id:      UUID
    data:         str
    card_type:    CardType
    srs_queue:    Optional[int] = None
    srs_due:      Optional[int] = None
    srs_factor:   Optional[int] = None
    srs_left:     Optional[int] = None
    srs_ivl:      Optional[int] = None
    srs_reps:     Optional[int] = None
    srs_lapses:   Optional[int] = None
    srs_data:     str = "{}"

    model_config = ConfigDict(from_attributes=True)


class ReviewSessionResponse(BaseModel):
    cards: List[CardResponse]
    total: int


class ReviewSessionWithSrsResponse(BaseModel):
    cards: List[CardWithSrsResponse]
    total: int
