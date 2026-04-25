from pydantic import BaseModel,ConfigDict
from typing import List, Tuple, Optional
from uuid import UUID


class WordEntry(BaseModel):
    id: UUID
    word: str
    reading: str
    meaning: str



class WordResponse(BaseModel):
    id:      UUID
    word:    str
    reading: str
    meaning: str

    model_config = ConfigDict(from_attributes=True)

class KanjiResponse(BaseModel):
    id: UUID
    kanji: str
    reading: Optional[str] = None
    strokes: Optional[int] = None
    radical: Optional[str] = None
    unicode: Optional[str] = None
    shape: Optional[str] = None
    meanings: Optional[str] = None   # newline-joined
    words: List[WordResponse] = []
 
    model_config = ConfigDict(from_attributes=True)
 


class Token(BaseModel):
    # sentence grouping
    sentence_id: int

    # surface forms
    surface: str
    normalized: str
    dictionary_form: str
    reading: Optional[str] = None

    # Sudachi POS (tuple like: ["名詞", ...])
    pos: Tuple[str, ...]

    # dictionary-level identifier
    word_id: int

    # character span in original text
    begin: int
    end: int

    # dictionary lookup result — None if the word isn't in our DB
    entry: Optional[WordEntry] = None


class TokenList(BaseModel):
    tokens: List[Token]