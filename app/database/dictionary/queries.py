"""
database/flashcard/queries.py
"""

from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlmodel import Session, select, func, case, col

from .schema import  Word, Kanji, WordKanjiReading
from ..flashcard.schema import Card, Deck, ReviewLog,State
# =========================================================
# DICTIONARY QUERIES (Word / Kanji)
# =========================================================
 
def add_word(session: Session, word: str, reading: str, meaning: str) -> Word:
    entry = Word(word=word, reading=reading, meaning=meaning)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry
 
 
def add_kanji(session: Session, kanji: str, reading: Optional[str] = None) -> Kanji:
    from typing import Optional  # local import guard
    entry = Kanji(kanji=kanji, reading=reading)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry
 
 
def link_word_kanji(session: Session, word_id: UUID, kanji_id: UUID) -> WordKanjiReading:
    link = WordKanjiReading(word_id=word_id, kanji_id=kanji_id)
    session.add(link)
    session.commit()
    session.refresh(link)
    return link
 
 
def look_up_words(session: Session, query: str, limit: int = 20) -> List[Word]:
    return session.exec(
        select(Word)
        .where(
            Word.word.contains(query) |
            Word.reading.contains(query) |
            Word.meaning.contains(query)
        )
        .limit(limit)
    ).all()
 
 
def look_up_word_exact(session: Session, query: str) -> Optional[Word]:
    return session.exec(
        select(Word).where((Word.word == query) | (Word.reading == query))
    ).first()
 
 
from typing import Optional  # ensure available at module level
 
 
def look_up_kanji(session: Session, kanji: str) -> Optional[Kanji]:
    return session.exec(select(Kanji).where(Kanji.kanji == kanji)).first()
 
 
def look_up_kanji_by_reading(session: Session, reading: str, limit: int = 20) -> List[Kanji]:
    return session.exec(
        select(Kanji).where(Kanji.reading.contains(reading)).limit(limit)
    ).all()
 
 
def get_words_for_kanji(session: Session, kanji_id: UUID) -> List[Word]:
    """All words in the dictionary that contain this kanji character."""
    return session.exec(
        select(Word)
        .join(WordKanjiReading, WordKanjiReading.word_id == Word.id)
        .where(WordKanjiReading.kanji_id == kanji_id)
    ).all()
 