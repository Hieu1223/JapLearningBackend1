from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from typing import Optional


class Word(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    word: str
    reading: str
    meaning: str


class Kanji(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    kanji: str
    reading: Optional[str] = None


# bridge table
class WordKanjiReading(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    word_id: UUID = Field(foreign_key="word.id")
    kanji_id: UUID = Field(foreign_key="kanji.id")