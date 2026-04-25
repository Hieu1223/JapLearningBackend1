"""
flashcard/schema.py  (API layer — Pydantic models)
"""

from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal
from enum import Enum

from ..database.flashcard.schema import State


# =========================================================
# STATE ENUM (API layer)
# =========================================================

class CardState(str, Enum):
    NEW        = "new"
    LEARNING   = "learning"
    REVIEW     = "review"
    RELEARNING = "relearning"


_STATE_MAP: dict[int, CardState] = {
    State.New:        CardState.NEW,
    State.Learning:   CardState.LEARNING,
    State.Review:     CardState.REVIEW,
    State.Relearning: CardState.RELEARNING,
}


def db_state_to_card_state(state: State) -> CardState:
    return _STATE_MAP[int(state)]


# =========================================================
# REQUEST MODELS
# =========================================================

class AddCardRequest(BaseModel):
    deck_id: UUID
    word_id: UUID


class ReviewRequest(BaseModel):
    card_id: UUID
    rating:  Literal["again", "hard", "good", "easy"]


# =========================================================
# WORD / DICTIONARY
# =========================================================

class WordResponse(BaseModel):
    id:      UUID
    word:    str
    reading: str
    meaning: str

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DECK
# =========================================================

class DeckResponse(BaseModel):
    id:       UUID
    name:     str
    owner_id: UUID
    public:   bool

    model_config = ConfigDict(from_attributes=True)


class DeckStatsResponse(BaseModel):
    new:        int = 0
    learning:   int = 0
    review:     int = 0
    relearning: int = 0
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
    review:     int
    relearning: int
    due:        int


class PublicDeckResponse(BaseModel):
    id:         UUID
    name:       str
    owner_id:   UUID
    card_count: int

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# CARD  (includes word data + SR state)
# =========================================================

class CardResponse(BaseModel):
    id:      UUID
    deck_id: UUID
    word:    WordResponse   # joined from Word table

    state:       CardState
    step:        Optional[int]   = None
    stability:   Optional[float] = None
    difficulty:  Optional[float] = None
    due:         datetime
    last_review: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# STATISTICS
# =========================================================

class DailyStatResponse(BaseModel):
    date:     str    # "YYYY-MM-DD"
    total:    int
    correct:  int
    wrong:    int
    accuracy: float


class OverviewStatsResponse(BaseModel):
    total_decks:    int
    total_cards:    int
    due_cards:      int
    new_cards:      int
    reviews_today:  int
    accuracy:       float
    streak_days:    int