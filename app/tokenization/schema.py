from pydantic import BaseModel, ConfigDict
from typing import List, Tuple, Optional
from uuid import UUID


class WordEntry(BaseModel):
    id: UUID
    word: str
    reading: str
    meaning: str


class WordResponse(BaseModel):
    id: UUID
    word: str
    reading: str
    meaning: str

    model_config = ConfigDict(from_attributes=True)


class WordLookupResponse(BaseModel):
    query: str
    results: List[WordResponse]
    total: int

    model_config = ConfigDict(from_attributes=True)


class KanjiResponse(BaseModel):
    id: UUID
    kanji: str
    reading: Optional[str] = None
    strokes: Optional[int] = None
    radical: Optional[str] = None
    unicode: Optional[str] = None
    shape: Optional[str] = None
    meanings: Optional[str] = None
    words: List[WordResponse] = []
  
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    sentence_id: int
    surface: str
    normalized: str
    dictionary_form: str
    reading: Optional[str] = None
    pos: Tuple[str, ...]
    word_id: int
    begin: int
    end: int


class TokenList(BaseModel):
    tokens: List[Token]