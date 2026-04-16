import json
from sqlmodel import Session, select, col
from uuid import UUID
from .schema import Manga, Chapter, QueryVRFToken, ReadHistory

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
            # Update fields if chapter already exists
            existing.title = chapter.title
            existing.num = chapter.num
            # We don't overwrite ocr_data or image_list unless provided in 'chapter'
            if chapter.ocr_data: existing.ocr_data = chapter.ocr_data
            if chapter.image_list != "{}": existing.image_list = chapter.image_list
            session.add(existing)
    session.commit()

def get_cached_chapter_info(session: Session, chapter_url: str) -> Chapter | None:
    """Retrieves a single chapter's metadata by its link."""
    statement = select(Chapter).where(Chapter.link == chapter_url)
    return session.exec(statement).first()

def update_chapter_pages(session: Session, chapter_id: UUID, pages: list[str]):
    """Updates the image_list for a chapter. Expects a list of URL strings."""
    chapter = session.get(Chapter, chapter_id)
    if chapter:
        chapter.image_list = json.dumps(pages)
        session.add(chapter)
        session.commit()

def get_cached_pages(session: Session, chapter_id: UUID) -> list[str]:
    """Retrieves the list of image URLs for a chapter."""
    chapter = session.get(Chapter, chapter_id)
    if chapter and chapter.image_list:
        return json.loads(chapter.image_list)
    return []

def update_chapter_ocr(session: Session, chapter_id: UUID, ocr_data: str):
    """
    Updates the OCR result and marks the chapter as transcripted.
    """
    chapter = session.get(Chapter, chapter_id)
    if not chapter:
        raise Exception(f"Cannot update OCR: Chapter {chapter_id} not found.")
    
    chapter.ocr_data = ocr_data
    chapter.transcripted = True
    
    session.add(chapter)
    session.commit()
    session.refresh(chapter)
    return chapter

# ── History ───────────────────────────────────────────────────────────────────

def get_read_histories(session: Session, user_id: UUID) -> list[Manga]:
    """Returns a list of Manga objects found in the user's read history."""
    statement = (
        select(Manga)
        .join(ReadHistory, ReadHistory.manga_id == Manga.id)
        .where(ReadHistory.user_id == user_id)
    )
    return list(session.exec(statement).all())