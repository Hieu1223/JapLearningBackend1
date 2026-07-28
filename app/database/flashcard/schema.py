from sqlmodel import SQLModel, Field
from enum import IntEnum
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional


class State(IntEnum):
    New        = 0
    Learning   = 1
    Review     = 2
    Relearning = 3


class Deck(SQLModel, table=True):
    id:       UUID = Field(default_factory=uuid4, primary_key=True)
    name:     str
    owner_id: UUID = Field(foreign_key="user.id")
    public:   bool = Field(default=False)
  

class Card(SQLModel, table=True):
    id:      UUID = Field(default_factory=uuid4, primary_key=True)
    deck_id: UUID = Field(foreign_key="deck.id")
    word_id: Optional[UUID] = Field(default=None, foreign_key="word.id")

    front: str = Field(default="")
    back: str = Field(default="")

    state:       State           = Field(default=State.New)
    step:        Optional[int]   = Field(default=0)
    stability:   Optional[float] = Field(default=None)
    difficulty:  Optional[float] = Field(default=None)
    due:         datetime        = Field(default_factory=datetime.utcnow)
    last_review: Optional[datetime] = Field(default=None)
  

class ReviewLog(SQLModel, table=True):
    id:      UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    card_id: UUID = Field(foreign_key="card.id")
    deck_id: UUID = Field(foreign_key="deck.id")
    word_id: Optional[UUID] = Field(default=None, foreign_key="word.id")

    state_before: State
    state_after:  State
    rating:       int

    reviewed_at: datetime = Field(default_factory=datetime.utcnow)