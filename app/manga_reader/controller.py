import json
from uuid import UUID
from typing import Optional, AsyncIterator
from sqlmodel import Session
from datetime import datetime, timezone
from fastapi import BackgroundTasks

from ..database.manga_reader.queries import (
    get_manga_list,
    search_manga,
    get_manga_by_id,
    get_chapter_by_id,
    get_chapters_for_manga,
    get_ocr_result_with_user,
    get_ocr_pages_for_chapter,
    save_ocr_page,
    delete_ocr_result,
    get_read_histories,
    upsert_read_history,
    delete_read_history,
    list_genres_by_ids,
)
from .schema import (
    OCRResponse,
    OCRPage,
    MangaPreview,
    MangaDetail,
    ChapterPreview,
    GenrePreview,
    ReadResponse,
    OCRResultResponse,
    OCRUserInfo,
    ReadHistoryResponse,
)
from .manga_ocr import do_ocr_stream, analyze_ocr_page


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _manga_preview(manga) -> MangaPreview:
    return MangaPreview(
        id=manga.id,
        title=manga.title,
        cover=manga.cover,
        status=manga.status,
    )


def _chapter_preview(chapter) -> ChapterPreview:
    return ChapterPreview(
        id=chapter.id,
        title=chapter.title,
        chapter_index=chapter.chapter_index,
        date=chapter.date,
    )


def _expand_pages_to_urls(payload: dict) -> list[str]:
    """
    Expands a stored pages payload back into a flat list of image URLs
    for use by the OCR layer.
    """
    t = payload.get("type")

    if t == "direct":
        return payload.get("images", [])

    if t == "template":
        base_url = payload["base_url"]
        page_count = payload["page_count"]
        pattern = payload["pattern"]
        return [f"{base_url}{pattern.format(i)}" for i in range(1, page_count + 1)]

    return []  # "empty"


# ─────────────────────────────────────────────────────────────
# MANGA LIST / SEARCH
# ─────────────────────────────────────────────────────────────

def ctrl_get_manga_list(
    session: Session,
    query: Optional[str],
    limit: int,
    offset: int,
) -> list[MangaPreview]:
    if query:
        mangas = search_manga(session, query, limit, offset)
    else:
        mangas = get_manga_list(session, limit, offset)
    return [_manga_preview(m) for m in mangas]


# ─────────────────────────────────────────────────────────────
# AGGREGATE MANGA (detail + chapter list)
# ─────────────────────────────────────────────────────────────

def _genre_preview(genre) -> GenrePreview:
    return GenrePreview(
        id=genre.id,
        slug=genre.slug,
        name=genre.name,
    )


def ctrl_get_manga_detail(session: Session, manga_id: UUID) -> Optional[MangaDetail]:
    manga = get_manga_by_id(session, manga_id)
    if not manga:
        return None

    chapters = get_chapters_for_manga(session, manga_id)

    return MangaDetail(
        id=manga.id,
        title=manga.title,
        cover=manga.cover,
        status=manga.status,
        description=manga.description,
        genres=[_genre_preview(g) for g in list_genres_by_ids(session, manga.genre_ids or [])],
        chapters=[_chapter_preview(c) for c in chapters],
    )


# ─────────────────────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────────────────────

def ctrl_read_chapter(session: Session, chapter_id: UUID) -> Optional[ReadResponse]:
    chapter = get_chapter_by_id(session, chapter_id)
    if not chapter:
        return None

    manga = get_manga_by_id(session, chapter.manga_id)
    if not manga:
        return None

    chapters = get_chapters_for_manga(session, manga.id)

    # expand the stored payload dict into a flat list of URLs
    payload = json.loads(chapter.pages) if chapter.pages else {"type": "empty"}
    pages = _expand_pages_to_urls(payload)

    return ReadResponse(
        manga=_manga_preview(manga),
        chapter=_chapter_preview(chapter),
        chapters=[_chapter_preview(c) for c in chapters],
        pages=pages,
    )


# ─────────────────────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────────────────────

def ctrl_get_existing_ocr(
    session: Session,
    chapter_id: UUID,
    offset: int = 0,
    limit: int = 50,
) -> Optional[OCRResultResponse]:
    row = get_ocr_result_with_user(session, chapter_id, offset, limit)
    if not row:
        return None

    window, ocr_by = row

    chapter = get_chapter_by_id(session, chapter_id)
    if not chapter:
        return None

    manga = get_manga_by_id(session, chapter.manga_id)
    if not manga:
        return None

    all_pages = [json.loads(p.ocr_data) for p in window]
    total_pages = len(get_ocr_pages_for_chapter(session, chapter_id))

    return OCRResultResponse(
        chapter_id=chapter_id,
        ocr_date=window[-1].ocr_date if window else datetime.now(timezone.utc),
        ocr_by=OCRUserInfo(id=ocr_by) if ocr_by else None,
        total_pages=total_pages,
        offset=offset,
        limit=limit,
        ocr_data=OCRResponse(pages=[OCRPage.model_validate(p) for p in all_pages]),
    )


async def ctrl_stream_ocr(
    session: Session,
    chapter_id: UUID,
    user_id: UUID,
    background_tasks: BackgroundTasks,
) -> AsyncIterator[str]:
    """
    Expands the stored pages payload into image URLs, streams OCR
    page-by-page as SSE events, and saves to DB via a background task
    so the save completes even if the client disconnects early.
    """
    chapter = get_chapter_by_id(session, chapter_id)
    if not chapter or not chapter.pages:
        raise ValueError("Chapter has no pages to OCR")

    payload = json.loads(chapter.pages)
    image_urls = _expand_pages_to_urls(payload)

    if not image_urls:
        raise ValueError("Chapter has no pages to OCR")

    accumulated: list[tuple[int, dict]] = []

    def _save_to_db():
        for page_number, analyzed in accumulated:
            save_ocr_page(
                session,
                chapter_id=chapter_id,
                page_number=page_number,
                ocr_data=json.dumps(analyzed),
                ocr_by=user_id,
            )

    background_tasks.add_task(_save_to_db)

    async for idx, page in enumerate(do_ocr_stream(image_urls)):
        analyzed = analyze_ocr_page(page)
        accumulated.append((idx, analyzed.model_dump()))
        yield f"data: {json.dumps(analyzed.model_dump())}\n\n"

    yield "data: [DONE]\n\n"


def ctrl_reset_ocr(
    session: Session,
    chapter_id: UUID,
) -> bool:
    return delete_ocr_result(session, chapter_id)


# ─────────────────────────────────────────────────────────────
# HISTORY
# ─────────────────────────────────────────────────────────────

def ctrl_get_history(session: Session, user_id: UUID) -> list[ReadHistoryResponse]:
    rows = get_read_histories(session, user_id)
    return [
        ReadHistoryResponse(
            id=row.id,
            current_page=row.current_page,
            updated_at=row.updated_at,
            manga_id=row.manga_id,
            manga_title=row.manga_title,
            manga_cover=row.manga_cover,
            chapter_id=row.chapter_id,
            chapter_index=row.chapter_index,
        )
        for row in rows
    ]


def ctrl_upsert_history(
    session: Session,
    user_id: UUID,
    manga_id: UUID,
    chapter_id: UUID,
    current_page: int,
) -> ReadHistoryResponse:
    manga = get_manga_by_id(session, manga_id)
    if not manga:
        raise ValueError("Manga not found")

    chapter = get_chapter_by_id(session, chapter_id)
    if not chapter:
        raise ValueError("Chapter not found")

    history = upsert_read_history(session, user_id, manga_id, chapter_id, current_page)

    return ReadHistoryResponse(
        id=history.id,
        current_page=history.current_page,
        updated_at=history.updated_at,
        manga_id=manga.id,
        manga_title=manga.title,
        manga_cover=manga.cover,
        chapter_id=chapter.id,
        chapter_index=chapter.chapter_index,
    )

def ctr_delete_history(session: Session, user_id: UUID, manga_id : UUID):
    delete_read_history(session,user_id,manga_id)