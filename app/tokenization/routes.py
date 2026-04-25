from fastapi import APIRouter, Depends, Query
from typing import Annotated

from ..security import scheme
from .schema import TokenList ,KanjiResponse,WordResponse
from .tokenize import tokenize, Token
from ..database.db import get_session, Session
from ..database.dictionary.queries import look_up_kanji, get_words_for_kanji,look_up_kanji_by_reading
from fastapi import HTTPException
from typing import List

router = APIRouter(tags=["tokenization"])


@router.get("/tokenize", response_model=TokenList)
async def tokenize_endpoint(
    text: Annotated[str, Query(..., min_length=1)],
    tokens: list[Token] = Depends(tokenize),
    token=Depends(scheme),
):
    return TokenList(tokens=tokens)



@router.get("/kanji/{kanji}", response_model=KanjiResponse)
def get_kanji(
    kanji: str,
    session: Session = Depends(get_session),
):
    """Look up a single kanji character and return its data + all known words."""
    row = look_up_kanji(session, kanji)
    if not row:
        raise HTTPException(status_code=404, detail="Kanji not found")
    words = get_words_for_kanji(session, row.id)
    return KanjiResponse(
        id=row.id,
        kanji=row.kanji,
        reading=row.reading,
        strokes=row.strokes,
        radical=row.radical,
        unicode=row.unicode,
        shape=row.shape,
        meanings=row.meanings,
        words=[WordResponse(id=w.id, word=w.word, reading=w.reading, meaning=w.meaning) for w in words],
    )
 
 
@router.get("/kanji", response_model=List[KanjiResponse])
def search_kanji(
    reading: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Search kanji by reading (Vietnamese romanization)."""
    rows = look_up_kanji_by_reading(session, reading, limit)
    result = []
    for row in rows:
        words = get_words_for_kanji(session, row.id)
        result.append(KanjiResponse(
            id=row.id,
            kanji=row.kanji,
            reading=row.reading,
            strokes=row.strokes,
            radical=row.radical,
            unicode=row.unicode,
            shape=row.shape,
            meanings=row.meanings,
            words=[WordResponse(id=w.id, word=w.word, reading=w.reading, meaning=w.meaning) for w in words],
        ))
    return result