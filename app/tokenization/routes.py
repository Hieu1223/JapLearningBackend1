from fastapi import APIRouter, Query, HTTPException
from typing import Annotated

from ..container import get_db_session
from ..security.auth import CurrentUser
from ..database.tokenization import (
    save_tokenization_history,
    get_user_tokenization_history,
    delete_tokenization_history,
)
from .schema import (
    WordLookupResponse,
    WordLookupEntry,
    TokenList,
    SaveTokenizationRequest,
    SaveTokenizationResponse,
    TokenizationHistoryItem,
    TokenizationHistoryListResponse,
)
from uuid import UUID
from .tokenize import tokenize
from .dictionary import get_dictionary
import json

router = APIRouter(tags=["tokenization"])


@router.get("/tokenize", response_model=TokenList, tags=["tokenization"], description="Split Japanese input text into morphological tokens and build the GiNZA dependency tree for each sentence")
async def tokenize_endpoint(
    text: Annotated[str, Query(..., min_length=1)],
):
    tokens, trees = await tokenize(text)
    return TokenList(tokens=tokens, sentences=trees)


@router.post(
    "/tokenize/save",
    response_model=SaveTokenizationResponse,
    tags=["tokenization"],
    description="Tokenize and build the dependency tree for the input text, then save both to the user's unified tokenization history and return them",
)
async def save_tokenization(
    req: SaveTokenizationRequest,
    user: CurrentUser,
):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    tokens, trees = await tokenize(req.text)

    session = get_db_session()
    history = save_tokenization_history(
        session,
        user,
        req.text,
        json.dumps(
            {
                "tokens": [t.model_dump() for t in tokens],
                "trees": [s.model_dump() for s in trees],
            },
            ensure_ascii=False,
        ),
        sentence_count=len(trees),
    )

    return SaveTokenizationResponse(
        history_id=history.id,
        tokens=tokens,
        sentences=trees,
    )


@router.get(
    "/tokenize/history",
    response_model=TokenizationHistoryListResponse,
    tags=["tokenization"],
    description="Return the current user's saved tokenization history (tokens + dependency trees)",
)
async def get_tokenization_history(
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    session = get_db_session()
    rows = get_user_tokenization_history(session, user, offset, limit)
    items = [
        TokenizationHistoryItem(
            history_id=r.id,
            text=r.text,
            sentence_count=r.sentences,
            date_created=r.date_created,
        )
        for r in rows
    ]
    return TokenizationHistoryListResponse(items=items, total=len(items))


@router.delete(
    "/tokenize/history/{history_id}",
    tags=["tokenization"],
    status_code=204,
    description="Delete a single entry from the current user's tokenization history",
)
async def delete_tokenization_history(
    history_id: UUID,
    user: CurrentUser,
):
    session = get_db_session()
    deleted = delete_tokenization_history(session, history_id, user)
    if not deleted:
        raise HTTPException(status_code=404, detail="History entry not found")
    return None


@router.get("/dictionary/words/lookup", response_model=WordLookupResponse, tags=["tokenization"], description="Search the Japanese dictionary by word or reading and return matching entries with meanings")
def lookup_words(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    dictionary = get_dictionary()
    results = dictionary.search(q, limit)
    entries = [
        WordLookupEntry(
            id=e["id"],
            word=e["word"],
            reading=e["kana"],
            meaning=e["suggest_mean"],
        )
        for e in results
    ]
    return WordLookupResponse(query=q, results=entries, total=len(entries))

