import json
from sqlmodel import Session, select
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional

from .schema import Manga, Chapter, OCRResult, ReadHistory, User


# ─────────────────────────────────────────────────────────────
# MANGA
# ─────────────────────────────────────────────────────────────

def get_manga_list(session: Session, limit: int = 20, offset: int = 0) -> list[Manga]:
    stmt = select(Manga).limit(limit).offset(offset)
    return list(session.exec(stmt).all())


def search_manga(session: Session, query: str, limit: int = 20, offset: int = 0) -> list[Manga]:
    stmt = (
        select(Manga)
        .where(Manga.title.ilike(f"%{query}%"))
        .limit(limit)
        .offset(offset)
    )
    return list(session.exec(stmt).all())


def get_manga_by_id(session: Session, manga_id: UUID) -> Optional[Manga]:
    return session.get(Manga, manga_id)


def get_manga_with_chapters(session: Session, manga_id: UUID) -> Optional[Manga]:
    """Returns manga with chapters eagerly loaded via relationship."""
    manga = session.get(Manga, manga_id)
    if manga:
        # touch the relationship to trigger load
        _ = manga.chapters
    return manga


def upsert_manga(
    session: Session,
    manga_id: UUID,
    url: str,
    slug: str,
    title: str,
    cover: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    genres: Optional[str] = None,
) -> Manga:
    manga = session.get(Manga, manga_id)

    if manga:
        manga.title = title or manga.title
        manga.cover = cover or manga.cover
        manga.description = description or manga.description
        manga.status = status or manga.status
        manga.genres = genres or manga.genres
        manga.updated_at = datetime.now(timezone.utc)
    else:
        manga = Manga(
            id=manga_id,
            url=url,
            slug=slug,
            title=title,
            cover=cover,
            description=description,
            status=status,
            genres=genres,
        )
        session.add(manga)

    session.commit()
    session.refresh(manga)
    return manga


# ─────────────────────────────────────────────────────────────
# CHAPTERS
# ─────────────────────────────────────────────────────────────

def get_chapter_by_id(session: Session, chapter_id: UUID) -> Optional[Chapter]:
    return session.get(Chapter, chapter_id)


def get_chapters_for_manga(session: Session, manga_id: UUID) -> list[Chapter]:
    stmt = (
        select(Chapter)
        .where(Chapter.manga_id == manga_id)
        .order_by(Chapter.chapter_index)
    )
    return list(session.exec(stmt).all())


def get_chapter_pages(session: Session, chapter_id: UUID) -> list[str]:
    chapter = session.get(Chapter, chapter_id)
    if chapter and chapter.pages:
        return json.loads(chapter.pages)
    return []


def upsert_chapter(
    session: Session,
    chapter_id: UUID,
    manga_id: UUID,
    url: str,
    title: str = "",
    chapter_index: Optional[int] = None,
    date: Optional[str] = None,
    pages: Optional[list[str]] = None,
) -> Chapter:
    chapter = session.get(Chapter, chapter_id)

    if chapter:
        chapter.title = title or chapter.title
        chapter.chapter_index = chapter_index if chapter_index is not None else chapter.chapter_index
        chapter.date = date or chapter.date
        if pages is not None:
            chapter.pages = json.dumps(pages)
    else:
        chapter = Chapter(
            id=chapter_id,
            manga_id=manga_id,
            url=url,
            title=title,
            chapter_index=chapter_index,
            date=date,
            pages=json.dumps(pages or []),
        )
        session.add(chapter)

    session.commit()
    session.refresh(chapter)
    return chapter


# ─────────────────────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────────────────────

def get_ocr_result(session: Session, chapter_id: UUID) -> Optional[OCRResult]:
    stmt = select(OCRResult).where(OCRResult.chapter_id == chapter_id)
    return session.exec(stmt).first()


def get_ocr_result_with_user(
    session: Session, chapter_id: UUID
) -> Optional[tuple[OCRResult, Optional[User]]]:
    result = get_ocr_result(session, chapter_id)
    if not result:
        return None
    user = session.get(User, result.ocr_by) if result.ocr_by else None
    return result, user


def save_ocr_result(
    session: Session,
    chapter_id: UUID,
    ocr_data: str,
    ocr_by: Optional[UUID] = None,
) -> OCRResult:
    existing = get_ocr_result(session, chapter_id)

    if existing:
        existing.ocr_data = ocr_data
        existing.ocr_by = ocr_by
        existing.ocr_date = datetime.now(timezone.utc)
        session.add(existing)
    else:
        existing = OCRResult(
            chapter_id=chapter_id,
            ocr_data=ocr_data,
            ocr_by=ocr_by,
        )
        session.add(existing)

    session.commit()
    session.refresh(existing)
    return existing


# ─────────────────────────────────────────────────────────────
# HISTORY
# ─────────────────────────────────────────────────────────────

class ReadHistoryRow:
    """Flat projection of history + manga + chapter for response building."""

    def __init__(self, history: ReadHistory, manga: Manga, chapter: Chapter):
        self.id = history.id
        self.user_id = history.user_id
        self.current_page = history.current_page
        self.updated_at = history.updated_at

        self.manga_id = manga.id
        self.manga_title = manga.title
        self.manga_cover = manga.cover

        self.chapter_id = chapter.id
        self.chapter_index = chapter.chapter_index


def get_read_histories(session: Session, user_id: UUID) -> list[ReadHistoryRow]:
    stmt = (
        select(ReadHistory, Manga, Chapter)
        .join(Manga, ReadHistory.manga_id == Manga.id)
        .join(Chapter, ReadHistory.chapter_id == Chapter.id)
        .where(ReadHistory.user_id == user_id)
        .order_by(ReadHistory.updated_at.desc())
    )
    rows = session.exec(stmt).all()
    return [ReadHistoryRow(h, m, c) for h, m, c in rows]


def upsert_read_history(
    session: Session,
    user_id: UUID,
    manga_id: UUID,
    chapter_id: UUID,
    current_page: int = 0,
) -> ReadHistory:
    stmt = select(ReadHistory).where(
        ReadHistory.user_id == user_id,
        ReadHistory.manga_id == manga_id,
    )
    history = session.exec(stmt).first()

    if history:
        history.chapter_id = chapter_id
        history.current_page = current_page
        history.updated_at = datetime.now(timezone.utc)
    else:
        history = ReadHistory(
            user_id=user_id,
            manga_id=manga_id,
            chapter_id=chapter_id,
            current_page=current_page,
        )
        session.add(history)

    session.commit()
    session.refresh(history)
    return history