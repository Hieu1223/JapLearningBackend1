from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Annotated, List
from uuid import UUID

from .schema import KanjiResponse, WordResponse, WordLookupResponse, TokenList
from .tokenize import tokenize
from ..database.db import Session, get_session
from ..database.dictionary.queries import look_up_kanji, get_words_for_kanji, look_up_kanji_by_reading, look_up_words, look_up_word_exact
from ..database.dictionary.schema import Word

router = APIRouter(tags=["tokenization"])


@router.get("/tokenize", response_model=TokenList)
async def tokenize_endpoint(
    text: Annotated[str, Query(..., min_length=1)],
):
    tokens = await tokenize(text)
    return TokenList(tokens=tokens)


@router.get("/dictionary/words/{word_id}", response_model=WordResponse)
def get_word(
    word_id: str,
    session: Session = Depends(get_session),
):
    word = session.get(Word, UUID(word_id))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return WordResponse(id=word.id, word=word.word, reading=word.reading, meaning=word.meaning)


@router.get("/dictionary/words/lookup", response_model=WordLookupResponse)
def lookup_words(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    words = look_up_words(session, q, limit)
    results = [WordResponse(id=w.id, word=w.word, reading=w.reading, meaning=w.meaning) for w in words]
    return WordLookupResponse(query=q, results=results, total=len(results))


@router.get("/dictionary/words/exact", response_model=WordResponse)
def get_exact_word(
    q: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
):
    word = look_up_word_exact(session, q)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return WordResponse(id=word.id, word=word.word, reading=word.reading, meaning=word.meaning)


@router.get("/kanji/{kanji}", response_model=KanjiResponse)
def get_kanji(
    kanji: str,
    session: Session = Depends(get_session),
):
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