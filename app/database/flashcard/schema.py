from sqlmodel import SQLModel, Field, Session, select
from enum import IntEnum
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional


class State(IntEnum):
    New = 0          # Added — cards that have never been reviewed
    Learning = 1
    Review = 2
    Relearning = 3


class Deck(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    owner_id: UUID = Field(foreign_key="user.id")
    public: bool = Field(default=False)


class Card(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    deck_id: UUID = Field(foreign_key="deck.id")
    front: str
    back: str  # Stored but never returned to client


class UserSavedDeck(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    deck_id: UUID = Field(foreign_key="deck.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CardSRData(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_saved_deck_id: UUID = Field(foreign_key="usersaveddeck.id")
    card_id: UUID = Field(foreign_key="card.id")

    state: State = Field(default=State.New)   # Changed default: new cards start as New
    step: Optional[int] = Field(default=0)
    stability: Optional[float] = Field(default=None)
    difficulty: Optional[float] = Field(default=None)
    due: datetime = Field(default_factory=datetime.utcnow)
    last_review: Optional[datetime] = Field(default=None)


class ReviewLog(SQLModel, table=True):
    """
    Immutable record written once per review action.
    Used for accurate daily stats, streaks, and accuracy calculations
    independent of the current CardSRData state.
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    card_id: UUID = Field(foreign_key="card.id")
    user_saved_deck_id: UUID = Field(foreign_key="usersaveddeck.id")

    # Snapshot of state BEFORE this review
    state_before: State
    # State AFTER applying SRS
    state_after: State

    # 1=Again  2=Hard  3=Good  4=Easy
    rating: int

    reviewed_at: datetime = Field(default_factory=datetime.utcnow)