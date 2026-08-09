from fastapi import APIRouter, Query
from typing import Annotated

from .schema import WordLookupResponse, WordLookupEntry, TokenList
from .tokenize import tokenize
from .dictionary import get_dictionary

router = APIRouter(tags=["tokenization"])


@router.get("/tokenize", response_model=TokenList, tags=["tokenization"], description="Split Japanese input text into morphological tokens for further lookup or study")
async def tokenize_endpoint(
    text: Annotated[str, Query(..., min_length=1)],
):
    tokens = await tokenize(text)
    return TokenList(tokens=tokens)


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

