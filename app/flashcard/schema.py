from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from uuid import UUID
from datetime import datetime, date
from typing import Optional, Literal
from enum import Enum

from ..database.flashcard import State


# =========================================================
# ENUM (API LAYER) — mirrors DB State including New
# =========================================================

class CardState(str, Enum):
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    RELEARNING = "relearning"


# Map DB IntEnum → API string enum
_STATE_MAP: dict[int, CardState] = {
    State.New: CardState.NEW,
    State.Learning: CardState.LEARNING,
    State.Review: CardState.REVIEW,
    State.Relearning: CardState.RELEARNING,
}


def db_state_to_card_state(state: State) -> CardState:
    return _STATE_MAP[int(state)]


# =========================================================
# REQUEST MODELS
# =========================================================

class AddCardRequest(BaseModel):
    deck_id: UUID
    front: str
    # back is intentionally omitted from the request;
    # the system stores front==back so both fields are the same.


class UpdateCardRequest(BaseModel):
    front: str


class ReviewRequest(BaseModel):
    sr_data_id: UUID
    rating: Literal["again", "hard", "good", "easy"]


# =========================================================
# DECK MODELS
# =========================================================

class DeckResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    public: bool

    model_config = ConfigDict(from_attributes=True)


class DeckStatsResponse(BaseModel):
    new: int = 0
    learning: int = 0
    review: int = 0
    relearning: int = 0
    due: int = 0


class DeckWithStatsResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    public: bool
    user_saved_deck_id: UUID
    stats: DeckStatsResponse

    model_config = ConfigDict(from_attributes=True)


class DeckProgressResponse(BaseModel):
    total: int
    new: int
    learning: int
    review: int
    relearning: int
    due: int


# =========================================================
# CARD MODELS
# front==back by design; back is NEVER exposed to the client
# =========================================================

class CardResponse(BaseModel):
    id: UUID
    deck_id: UUID
    front: str
    # back is deliberately excluded

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# SRS MODELS
# =========================================================

class CardSRDataResponse(BaseModel):
    sr_data_id: UUID          # renamed from `id` at the API layer
    card_id: UUID
    user_saved_deck_id: UUID

    front: str                # joined from Card; back is excluded

    state: CardState

    step: Optional[int] = None
    stability: Optional[float] = None
    difficulty: Optional[float] = None

    due: datetime
    last_review: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewResponse(BaseModel):
    sr_data_id: UUID

    state: CardState
    stability: Optional[float] = None
    difficulty: Optional[float] = None

    due: datetime
    last_review: Optional[datetime] = None

    interval_days: Optional[int] = None


# =========================================================
# STATISTICS MODELS
# =========================================================

class DailyStatResponse(BaseModel):
    date: str          # "YYYY-MM-DD"
    total: int
    correct: int
    wrong: int
    accuracy: float    # 0.0–1.0


class OverviewStatsResponse(BaseModel):
    total_decks: int
    total_cards: int

    due_cards: int
    new_cards: int

    reviews_today: int
    accuracy: float

    streak_days: int


# =========================================================
# USER OVERVIEW / DECK BROWSE
# =========================================================

class PublicDeckResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    card_count: int

    model_config = ConfigDict(from_attributes=True)