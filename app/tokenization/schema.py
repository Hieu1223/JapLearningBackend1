from pydantic import BaseModel


from pydantic import BaseModel
from typing import List, Tuple, Optional


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


class TokenList(BaseModel):
    tokens: List[Token]
