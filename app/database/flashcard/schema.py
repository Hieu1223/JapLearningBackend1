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
    """
    One row per (deck, word).  SR scheduling lives here directly.
    When a user copies a public deck every source Card is cloned into a
    new Card row under the new Deck — fully independent of the original.
    """
    id:      UUID = Field(default_factory=uuid4, primary_key=True)
    deck_id: UUID = Field(foreign_key="deck.id")
    word_id: UUID = Field(foreign_key="word.id")
 
    # SRS
    state:       State           = Field(default=State.New)
    step:        Optional[int]   = Field(default=0)
    stability:   Optional[float] = Field(default=None)
    difficulty:  Optional[float] = Field(default=None)
    due:         datetime        = Field(default_factory=datetime.utcnow)
    last_review: Optional[datetime] = Field(default=None)
 
 
class ReviewLog(SQLModel, table=True):
    """Immutable append-only record written once per review action."""
    id:      UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    card_id: UUID = Field(foreign_key="card.id")
    deck_id: UUID = Field(foreign_key="deck.id")
    word_id: UUID = Field(foreign_key="word.id")
 
    state_before: State
    state_after:  State
    rating:       int       # 1=Again  2=Hard  3=Good  4=Easy
 
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)