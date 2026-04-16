from sqlmodel import SQLModel, Field, Session, select
from enum import IntEnum
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

class State(IntEnum):
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
    back: str

class UserSavedDeck(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    deck_id: UUID = Field(foreign_key="deck.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CardSRData(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_saved_deck_id: UUID = Field(foreign_key="usersaveddeck.id")
    card_id: UUID = Field(foreign_key="card.id")
    
    state: State = Field(default=State.Learning)
    step: Optional[int] = Field(default=0)
    stability: Optional[float] = Field(default=None)
    difficulty: Optional[float] = Field(default=None)
    due: datetime = Field(default_factory=datetime.utcnow)
    last_review: Optional[datetime] = Field(default=None)