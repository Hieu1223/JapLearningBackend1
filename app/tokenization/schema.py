from pydantic import BaseModel, ConfigDict
from typing import List, Tuple, Optional
from uuid import UUID
from datetime import datetime


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
    dep: Optional[str] = None
    dep_description: Optional[str] = None
    head_index: Optional[int] = None
    head_surface: Optional[str] = None


class TokenList(BaseModel):
    tokens: List[Token]


class DependencyLink(BaseModel):
    token_index: int
    surface: str
    reading: Optional[str] = None
    lemma: str
    pos: Tuple[str, ...]
    dep: str
    dep_description: str
    head_index: Optional[int] = None
    head_surface: Optional[str] = None
    is_root: bool = False


class DependencyTree(BaseModel):
    sentence_id: int
    text: str
    tokens: List[DependencyLink]


class DependencyTreeResponse(BaseModel):
    text: str
    sentences: List[DependencyTree]


class TokenizeDependenciesRequest(BaseModel):
    text: str
    user_id: UUID


class TokenizeDependenciesResponse(BaseModel):
    history_id: UUID
    text: str
    sentences: List[DependencyTree]


class TokenizationHistoryItem(BaseModel):
    history_id: UUID
    text: str
    sentences: int
    date_created: datetime


class TokenizationHistoryListResponse(BaseModel):
    items: List[TokenizationHistoryItem]
    total: int