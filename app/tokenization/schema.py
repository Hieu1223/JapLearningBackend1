from pydantic import BaseModel, ConfigDict
from typing import List, Tuple, Optional
from uuid import UUID


class WordEntry(BaseModel):
    id: UUID
    word: str
    reading: str
    meaning: str


class WordLookupEntry(BaseModel):
    id: int
    word: str
    reading: str
    meaning: str

    model_config = ConfigDict(from_attributes=True)


class WordLookupResponse(BaseModel):
    query: str
    results: List[WordLookupEntry]
    total: int

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