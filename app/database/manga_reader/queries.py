import json
from sqlmodel import Session,delete, select, col
from uuid import UUID
from .schema import Manga, Chapter, QueryVRFToken, ReadHistory,NonceToken
from datetime import datetime, timezone,timedelta
from typing import Optional


# ── Search & VRF Cache ────────────────────────────────────────────────────────

def get_cached_search_vrf_token(session: Session, query: str) -> str | None:
    """Retrieves a cached VRF token for a specific search query string."""
    statement = select(QueryVRFToken).where(QueryVRFToken.query == query)
    result = session.exec(statement).first()
    return result.token if result else None


def update_cached_search_vrf_token(session: Session, query: str, vrf_token: str):
    """Updates existing token or creates a new entry for the search query."""
    statement = select(QueryVRFToken).where(QueryVRFToken.query == query)
    cache_item = session.exec(statement).first()

    if cache_item:
        cache_item.token = vrf_token
    else:
        cache_item = QueryVRFToken(query=query, token=vrf_token)

    session.add(cache_item)
    session.commit()


# ── Manga Info ────────────────────────────────────────────────────────────────

def get_cached_manga_info(session: Session, manga_urls: list[str]) -> list[Manga]:
    """Retrieves Manga records matching the provided URL list."""
    statement = select(Manga).where(col(Manga.manga_url).in_(manga_urls))
    return list(session.exec(statement).all())


def update_mangas_info(session: Session, mangas: list[Manga]):
    """Syncs manga metadata. Updates if manga_url exists, otherwise inserts."""
    for manga in mangas:
        statement = select(Manga).where(Manga.manga_url == manga.manga_url)
        existing = session.exec(statement).first()
        if existing:
            existing.manga_cover_url = manga.manga_cover_url
            if manga.name:
                existing.name = manga.name
            existing.has_transcripted_chapters = manga.has_transcripted_chapters
            session.add(existing)
        else:
            session.add(manga)
    session.commit()


# ── Chapters ──────────────────────────────────────────────────────────────────

def add_chapter_infos(session: Session, chapters: list[Chapter]):
    """Adds or updates chapters. Identification based on the link URL."""
    for chapter in chapters:
        statement = select(Chapter).where(Chapter.link == chapter.link)
        existing = session.exec(statement).first()
        if not existing:
            session.add(chapter)
        else:
            existing.title = chapter.title
            existing.num = chapter.num
            if chapter.ocr_data:
                existing.ocr_data = chapter.ocr_data
            if chapter.image_list not in ("{}", "[]", ""):
                existing.image_list = chapter.image_list
            session.add(existing)
    session.commit()


def get_cached_chapter_info(session: Session, chapter_url: str) -> Chapter | None:
    """Retrieves a single chapter's metadata by its link."""
    statement = select(Chapter).where(Chapter.link == chapter_url)
    return session.exec(statement).first()


def update_chapter_pages(session: Session, chapter_url: UUID, pages: list[str]):
    """Updates image_list using chapter link."""
    statement = select(Chapter).where(Chapter.link == chapter_url)
    chapter = session.exec(statement).first()

    if not chapter:
        return None  # or raise Exception if you want strict behavior

    chapter.image_list = json.dumps(pages)
    session.commit()
    session.refresh(chapter)
    return chapter


def get_cached_pages(session: Session, chapter_id: UUID) -> list[str]:
    """Retrieves the list of image URLs for a chapter."""
    chapter = session.get(Chapter, chapter_id)
    if chapter and chapter.image_list:
        return json.loads(chapter.image_list)
    return []


def update_chapter_ocr(session: Session, chapter_id: UUID, ocr_data: str):
    """Updates the OCR result and marks the chapter as transcripted."""
    chapter = session.get(Chapter, chapter_id)
    if not chapter:
        raise Exception(f"Cannot update OCR: Chapter {chapter_id} not found.")

    chapter.ocr_data = ocr_data
    chapter.transcripted = True
    session.commit()
    session.refresh(chapter)
    return chapter


# ── History ───────────────────────────────────────────────────────────────────

class ReadHistoryWithDetails:
    """In-memory joined result returned by get_read_histories."""

    def __init__(
        self,
        history: ReadHistory,
        manga: Manga,
        chapter: Chapter,
    ):
        self.id = history.id
        self.user_id = history.user_id
        self.current_page = history.current_page
        self.updated_at = history.updated_at

        # Manga fields
        self.manga_id = manga.id
        self.manga_url = manga.manga_url
        self.manga_name = manga.name
        self.manga_cover_url = manga.manga_cover_url

        # Chapter fields
        self.chapter_id = chapter.id
        self.chapter_url = chapter.link
        self.chapter_title = chapter.title
        self.chapter_num = chapter.num


def get_read_histories(
    session: Session, user_id: UUID
) -> list[ReadHistoryWithDetails]:
    """
    Returns enriched history records for the user (most recently updated first),
    joining Manga and Chapter for name, cover URL, and chapter title.
    """
    statement = (
        select(ReadHistory, Manga, Chapter)
        .join(Manga, ReadHistory.manga_id == Manga.id)
        .join(Chapter, ReadHistory.chapter_id == Chapter.id)
        .where(ReadHistory.user_id == user_id)
        .order_by(ReadHistory.updated_at.desc())
    )
    rows = session.exec(statement).all()
    return [
        ReadHistoryWithDetails(history=h, manga=m, chapter=c)
        for h, m, c in rows
    ]


def upsert_read_history_query(
    session: Session,
    user_id: UUID,
    manga_id: UUID,
    chapter_id: UUID,
    current_page: int = 0,
) -> ReadHistory:
    """
    Upserts a ReadHistory row keyed on (user_id, manga_id).
    Updates chapter_id, current_page, and updated_at on conflict.
    """
    statement = select(ReadHistory).where(
        ReadHistory.user_id == user_id,
        ReadHistory.manga_id == manga_id,
    )
    history_item = session.exec(statement).first()

    if history_item:
        history_item.chapter_id = chapter_id
        history_item.current_page = current_page
        history_item.updated_at = datetime.now(timezone.utc)
    else:
        history_item = ReadHistory(
            user_id=user_id,
            manga_id=manga_id,
            chapter_id=chapter_id,
            current_page=current_page,
        )
        session.add(history_item)

    session.commit()
    session.refresh(history_item)
    return history_item


# ── Convenience helpers ───────────────────────────────────────────────────────


def get_manga_with_url(
    session : Session,
    manga_url : str
):
    statement = select(Manga).where(Manga.manga_url == manga_url)
    manga = session.exec(statement).first()
    return manga


def get_or_create_manga(
    session: Session,
    manga_url: str,
    cover_url: str = "",
    name: str = "",
) -> Manga:
    statement = select(Manga).where(Manga.manga_url == manga_url)
    manga = session.exec(statement).first()

    if manga:
        # Keep metadata fresh when callers supply it
        if name and not manga.name:
            manga.name = name
        if cover_url and not manga.manga_cover_url:
            manga.manga_cover_url = cover_url
        session.add(manga)
        session.commit()
        session.refresh(manga)
        return manga

    manga = Manga(manga_url=manga_url, manga_cover_url=cover_url, name=name)
    session.add(manga)
    session.commit()
    session.refresh(manga)
    return manga


def get_or_create_chapter(
    session: Session,
    chapter_url: str,
    image_list: list[str] | None = None,
    ocr_data: str = "",
    title: str = "",
    num: str = "",
) -> Chapter:
    statement = select(Chapter).where(Chapter.link == chapter_url)
    chapter = session.exec(statement).first()

    if chapter:
        return chapter

    chapter = Chapter(
        link=chapter_url,
        image_list=json.dumps(image_list or []),
        ocr_data=ocr_data,
        title=title,
        num=num,
    )
    session.add(chapter)
    session.commit()
    session.refresh(chapter)
    return chapter


def upsert_chapter(
    session: Session,
    chapter_url: str,
    image_list: list[str] | None = None,
    ocr_data: str | None = None,
    title: str = "",
    num: str = "",
) -> Chapter:
    statement = select(Chapter).where(Chapter.link == chapter_url)
    chapter = session.exec(statement).first()

    if chapter:
        if title:
            chapter.title = title
        if num:
            chapter.num = num
        session.add(chapter)
    else:
        chapter = Chapter(
            link=chapter_url,
            image_list=json.dumps(image_list or []),
            ocr_data=ocr_data or "",
            title=title,
            num=num,
        )
        session.add(chapter)

    session.commit()
    session.refresh(chapter)
    return chapter



def get_nonce(db: Session) -> str:
    try:
        stmt = select(NonceToken).order_by(NonceToken.created_at.desc())
        token_obj = db.exec(stmt).first()
        return token_obj.token if token_obj else ""
    except Exception as e:
        print(f"[get_nonce] error: {e}")
        return ""
    

def refresh_nonce(db: Session, token: str) -> str:
    try:
        if not token:
            return ""

        db.exec(delete(NonceToken))  # wipe old
        db.add(NonceToken(token=token))
        db.commit()

        return token
    except Exception as e:
        print(f"[refresh_nonce] error: {e}")
        return ""