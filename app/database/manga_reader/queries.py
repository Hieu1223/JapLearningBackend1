import json
from sqlmodel import Session, select
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional

from .schema import Manga, Chapter, OCRResult, ReadHistory, Genre, Creator, MangaCreator
from ..user.schema import User


# ─────────────────────────────────────────────────────────────
# MANGA
# ─────────────────────────────────────────────────────────────

def _apply_manga_filters(
    stmt,
    query: Optional[str],
    tags: Optional[list[str]],
    author: Optional[UUID] = None,
):
    if query:
        stmt = stmt.where(Manga.title.ilike(f"%{query}%"))
    if tags:
        # tags arrive as genre slugs/names; resolve to ids via the genre table
        # then match any manga whose genre_ids array overlaps the resolved ids.
        resolved = select(Genre.id).where(Genre.slug.in_(tags) | Genre.name.in_(tags))
        stmt = stmt.where(Manga.genre_ids.op("&&")(resolved))
    if author:
        stmt = stmt.join(
            MangaCreator, MangaCreator.manga_id == Manga.id
        ).where(MangaCreator.creator_id == author)
    return stmt


def _apply_manga_order(stmt, order_by: Optional[str], order_dir: str = "desc"):
    desc = order_dir == "desc"
    key = order_by or "trending"
    if key in ("trending", "reader_count"):
        return stmt.order_by(Manga.reader_count.desc() if desc else Manga.reader_count)
    if key in ("az", "alphabet", "title"):
        return stmt.order_by(Manga.title.desc() if desc else Manga.title)
    if key in ("views", "view", "views_daily", "views_weekly", "views_monthly"):
        col = {
            "views_daily": Manga.views_daily,
            "views_monthly": Manga.views_monthly,
        }.get(key, Manga.views_weekly)
        return stmt.order_by(col.desc() if desc else col)
    if key in ("score",):
        return stmt.order_by(Manga.score.desc() if desc else Manga.score)
    if key in ("latest", "updated_at"):
        return stmt.order_by(Manga.updated_at.desc() if desc else Manga.updated_at)
    if key in ("created", "created_at"):
        return stmt.order_by(Manga.created_at.desc() if desc else Manga.created_at)
    return stmt.order_by(Manga.reader_count.desc())


def get_manga_list(
    session: Session,
    limit: int = 20,
    offset: int = 0,
    tags: Optional[list[str]] = None,
    author: Optional[UUID] = None,
    order_by: Optional[str] = None,
    order_dir: str = "desc",
) -> list[Manga]:
    stmt = select(Manga)
    stmt = _apply_manga_filters(stmt, None, tags, author=author)
    stmt = _apply_manga_order(stmt, order_by, order_dir)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.exec(stmt).all())


def search_manga(
    session: Session,
    query: str,
    limit: int = 20,
    offset: int = 0,
    tags: Optional[list[str]] = None,
    author: Optional[UUID] = None,
    order_by: Optional[str] = None,
    order_dir: str = "desc",
) -> list[Manga]:
    stmt = select(Manga)
    stmt = _apply_manga_filters(stmt, query, tags, author=author)
    stmt = _apply_manga_order(stmt, order_by, order_dir)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.exec(stmt).all())


def get_manga_by_id(session: Session, manga_id: UUID) -> Optional[Manga]:
    return session.get(Manga, manga_id)


def get_manga_creators(session: Session, manga_id: UUID) -> list[Creator]:
    stmt = (
        select(Creator)
        .join(MangaCreator, MangaCreator.creator_id == Creator.id)
        .where(MangaCreator.manga_id == manga_id)
        .order_by(Creator.role, Creator.name)
    )
    return list(session.exec(stmt).all())


def list_genres(
    session: Session,
    q: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Genre]:
    stmt = select(Genre)
    if q:
        q_lower = q.lower()
        stmt = stmt.where(Genre.slug.ilike(f"{q_lower}%") | Genre.name.ilike(f"{q_lower}%"))
    if order_by == "az":
        stmt = stmt.order_by(Genre.name)
    elif order_by == "-az":
        stmt = stmt.order_by(Genre.name.desc())
    else:
        stmt = stmt.order_by(Genre.name)
    stmt = stmt.limit(limit).offset(offset)
    return list(session.exec(stmt).all())


def list_creators(
    session: Session,
    q: Optional[str] = None,
    role: Optional[str] = None,
    order_by: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Creator]:
    stmt = select(Creator)
    if q:
        q_lower = q.lower()
        stmt = stmt.where(Creator.slug.ilike(f"{q_lower}%") | Creator.name.ilike(f"{q_lower}%"))
    if role:
        stmt = stmt.where(Creator.role == role)
    if order_by in ("az", None):
        stmt = stmt.order_by(Creator.name)
    elif order_by == "-az":
        stmt = stmt.order_by(Creator.name.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list(session.exec(stmt).all())


def get_manga_with_chapters(session: Session, manga_id: UUID) -> Optional[Manga]:
    """Returns manga with chapters eagerly loaded via relationship."""
    manga = session.get(Manga, manga_id)
    if manga:
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
    genre_ids: Optional[list[int]] = None,
) -> Manga:
    manga = session.get(Manga, manga_id)

    if manga:
        manga.title = title or manga.title
        manga.cover = cover or manga.cover
        manga.description = description or manga.description
        manga.status = status or manga.status
        manga.genre_ids = genre_ids or manga.genre_ids
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
            genre_ids=genre_ids or [],
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

def get_ocr_pages_for_chapter(session: Session, chapter_id: UUID) -> list[OCRResult]:
    """Return every OCR page row for a chapter ordered by page_number."""
    stmt = (
        select(OCRResult)
        .where(OCRResult.chapter_id == chapter_id)
        .order_by(OCRResult.page_number)
    )
    return list(session.exec(stmt).all())


def get_ocr_result_with_user(
    session: Session, chapter_id: UUID, offset: int = 0, limit: int = 50
) -> Optional[tuple[list[OCRResult], Optional[UUID]]]:
    pages = get_ocr_pages_for_chapter(session, chapter_id)
    if not pages:
        return None
    window = pages[offset:offset + limit]
    ocr_by = next((p.ocr_by for p in pages if p.ocr_by), None)
    return window, ocr_by


def save_ocr_page(
    session: Session,
    chapter_id: UUID,
    page_number: int,
    ocr_data: str,
    ocr_by: Optional[UUID] = None,
) -> OCRResult:
    stmt = select(OCRResult).where(
        OCRResult.chapter_id == chapter_id,
        OCRResult.page_number == page_number,
    )
    existing = session.exec(stmt).first()

    if existing:
        existing.ocr_data = ocr_data
        existing.ocr_by = ocr_by
        existing.ocr_date = datetime.now(timezone.utc)
        session.add(existing)
    else:
        existing = OCRResult(
            chapter_id=chapter_id,
            page_number=page_number,
            ocr_data=ocr_data,
            ocr_by=ocr_by,
        )
        session.add(existing)

    session.commit()
    session.refresh(existing)
    return existing


def delete_ocr_result(session: Session, chapter_id: UUID) -> bool:
    pages = get_ocr_pages_for_chapter(session, chapter_id)
    if not pages:
        return False
    for p in pages:
        session.delete(p)
    session.commit()
    return True


def delete_read_history_by_id(
    session: Session,
    history_id: UUID,
    user_id: UUID,
) -> bool:
    stmt = select(ReadHistory).where(
        ReadHistory.id == history_id,
        ReadHistory.user_id == user_id,
    )
    history = session.exec(stmt).first()

    if not history:
        return False

    session.delete(history)
    session.commit()
    return True


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


def get_read_history_by_id(
    session: Session, history_id: UUID, user_id: UUID
) -> Optional[ReadHistory]:
    stmt = select(ReadHistory).where(
        ReadHistory.id == history_id,
        ReadHistory.user_id == user_id,
    )
    return session.exec(stmt).first()


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


def delete_read_history(
    session: Session,
    user_id: UUID,
    manga_id: UUID,
) -> bool:
    stmt = select(ReadHistory).where(
        ReadHistory.user_id == user_id,
        ReadHistory.manga_id == manga_id,
    )
    history = session.exec(stmt).first()

    if not history:
        return False

    session.delete(history)
    session.commit()
    return True
    history = session.exec(stmt).first()

    if not history:
        return False

    session.delete(history)
    session.commit()
    return True


# ─────────────────────────────────────────────────────────────
# OCR BACKFILL (GiNZA analysis on existing OCR data)
# ─────────────────────────────────────────────────────────────

def get_all_ocr_results(session: Session) -> list[OCRResult]:
    return list(session.exec(select(OCRResult)).all())