from fastapi import APIRouter, Query, HTTPException

from ..database import SessionDep
from ..database.grammar import Grammar, search_grammar, get_grammar
from .schema import (
    GrammarSummary,
    GrammarEntry,
    GrammarLookupResponse,
    GrammarDetailResponse,
)

router = APIRouter(tags=["grammar"])


@router.get(
    "/lookup",
    response_model=GrammarLookupResponse,
    tags=["grammar"],
    description="Search Japanese grammar points by keyword (fast trigram index on the keyword column). Returns a summary: keyword, jp and meaning only.",
)
def lookup_grammar(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    session: SessionDep = None,
):
    rows = search_grammar(session, q, limit)
    results = [
        GrammarSummary(
            id=r.id,
            keyword=r.keyword,
            jp=r.jp,
            imi_setsumei=r.imi_setsumei,
        )
        for r in rows
    ]
    return GrammarLookupResponse(query=q, results=results, total=len(results))


@router.get(
    "/detail",
    response_model=GrammarDetailResponse,
    tags=["grammar"],
    description="Get the full grammar entry (meaning, usage formation and example sentences/reibun) by its id from a lookup result.",
)
def grammar_detail(
    id: int = Query(..., description="Grammar entry id returned by /lookup"),
    session: SessionDep = None,
):
    entry = get_grammar(session, id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Grammar entry not found")
    return GrammarDetailResponse(
        entry=GrammarEntry(
            id=entry.id,
            keyword=entry.keyword,
            jp=entry.jp,
            imi_setsumei=entry.imi_setsumei,
            tsukaikata_setsumei=entry.tsukaikata_setsumei,
            reibun=entry.reibun,
        )
    )
