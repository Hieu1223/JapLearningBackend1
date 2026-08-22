from typing import List

from pydantic import BaseModel


class ReibunItem(BaseModel):
    ja: str
    vn: str
    romaji: str


class GrammarSummary(BaseModel):
    id: int
    keyword: str
    jp: str
    imi_setsumei: str


class GrammarEntry(BaseModel):
    id: int
    keyword: str
    jp: str
    imi_setsumei: str
    tsukaikata_setsumei: str
    reibun: List[ReibunItem]


class GrammarLookupResponse(BaseModel):
    query: str
    results: List[GrammarSummary]
    total: int


class GrammarDetailResponse(BaseModel):
    entry: GrammarEntry
