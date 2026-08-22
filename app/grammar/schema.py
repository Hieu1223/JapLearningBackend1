from typing import List

from pydantic import BaseModel


class ReibunItem(BaseModel):
    ja: str
    vn: str
    romaji: str


class GrammarEntry(BaseModel):
    id: int
    keyword: str
    jp: str
    imi_setsumei: str
    tsukaikata_setsumei: str
    reibun: List[ReibunItem]


class GrammarLookupResponse(BaseModel):
    query: str
    results: List[GrammarEntry]
    total: int
