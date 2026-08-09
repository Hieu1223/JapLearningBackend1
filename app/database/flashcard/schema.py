from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ForeignKey, UUID as SQLUUID
from enum import IntEnum, Enum
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional


class Queue(IntEnum):
    New        = 0
    Learning   = 1
    Review     = 2
    Relearning = 3
    Suspended  = -1
    Buried     = -2


class CardType(str, Enum):
    VOCAB    = "vocab"
    GRAMMAR  = "grammar"
    SENTENCE = "sentence"


def make_sorting_id(card_type: CardType, **parts) -> str:
    """Build a stable sorting id used for ordering and duplicate detection.

    For vocab cards the id is ``<word>-vocab``; other types fall back to
    ``<type>`` with any provided parts appended.
    """
    if card_type == CardType.VOCAB:
        word = parts.get("word", "")
        return f"{word}-{card_type.value}"
    extra = "-".join(str(v) for v in parts.values() if v)
    return f"{card_type.value}-{extra}" if extra else card_type.value


class Deck(SQLModel, table=True):
    id:       UUID = Field(default_factory=uuid4, primary_key=True)
    name:     str
    owner_id: UUID = Field(foreign_key="user.id")
    public:   bool = Field(default=False)
  

class Card(SQLModel, table=True):
    id:         UUID = Field(default_factory=uuid4, primary_key=True)
    deck_id:    UUID = Field(foreign_key="deck.id")
    card_type:  CardType = Field(default=CardType.VOCAB)
    sorting_id: str = Field(index=True)

    data:       str = Field(default="{}")


class SrsCard(SQLModel, table=True):
    """FSRS scheduling state for a card, matching the ts-fsrs ``Card`` model.

    The frontend runs the ts-fsrs scheduler and persists the resulting card
    here. Field names mirror ts-fsrs so the JSON round-trips losslessly.
    """
    id:      UUID = Field(default_factory=uuid4, primary_key=True)
    card_id: UUID = Field(
        default=None,
        sa_column=Column(
            SQLUUID,
            ForeignKey("card.id", ondelete="CASCADE"),
            unique=True,
        ),
    )

    # ts-fsrs Card fields
    due:            datetime = Field(default_factory=datetime.utcnow)   # next review date
    stability:      float = Field(default=0.0)                          # memory stability
    difficulty:     float = Field(default=0.0)                          # difficulty (1-10)
    elapsed_days:   int  = Field(default=0)                             # days since last review
    scheduled_days: int  = Field(default=0)                             # days until next review
    learning_steps: int  = Field(default=0)                             # index into learning steps
    reps:           int  = Field(default=0)                             # repetition count
    lapses:         int  = Field(default=0)                             # number of lapses
    state:          int  = Field(default=0)                             # State: 0 New, 1 Learning, 2 Review, 3 Relearning
    last_review:    Optional[datetime] = Field(default=None)            # last review timestamp