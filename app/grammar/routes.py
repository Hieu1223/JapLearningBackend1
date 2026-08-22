from fastapi import APIRouter, Query
from typing import List, Optional

from pydantic import BaseModel

from ..database import SessionDep
from ..database.grammar import Grammar, search_grammar

router = APIRouter(tags=["grammar"])


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


@router.get(
    "/grammar/lookup",
    response_model=GrammarLookupResponse,
    tags=["grammar"],
    description="Search Japanese grammar points by keyword (fast trigram index on the keyword column). HTML markup in the fields is returned unmodified.",
)
def lookup_grammar(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    session: SessionDep = None,
):
    rows = search_grammar(session, q, limit)
    results = [
        GrammarEntry(
            id=r.id,
            keyword=r.keyword,
            jp=r.jp,
            imi_setsumei=r.imi_setsumei,
            tsukaikata_setsumei=r.tsukaikata_setsumei,
            reibun=r.reibun,
        )
        for r in rows
    ]
    return GrammarLookupResponse(query=q, results=results, total=len(results))
