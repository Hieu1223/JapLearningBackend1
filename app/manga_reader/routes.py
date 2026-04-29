from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

from ..database import SessionDep
from .rawkuma_extractor import NatsuExtractor
from .manga_ocr import do_ocr,do_ocr_stream
from .schema import MangaInfo, ChapterInfo, OCRResponse
from .sort_type import SortType
from ..database.manga_reader.queries import (
    upsert_read_history_query,
    get_read_histories,
    get_or_create_manga,
    get_or_create_chapter,
    get_manga_with_url
)
from ..security.auth import CurrentUser
import json
router = APIRouter(tags=["Manga"])


# ── Pydantic I/O models ───────────────────────────────────────────────────────

class ReadHistoryUpdate(BaseModel):
    """
    Callers send human-readable URLs; the route resolves them to DB IDs.
    manga_name and cover_url are used to create the Manga row if it doesn't
    exist yet (they are optional — existing rows won't be overwritten).
    """
    manga_url: str
    manga_name: Optional[str] = ""
    manga_cover_url: Optional[str] = ""
    chapter_url: str
    chapter_title: Optional[str] = ""
    chapter_num: Optional[str] = ""
    current_page: int = 0


class ReadHistoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    current_page: int
    updated_at: datetime

    # Manga
    manga_id: UUID
    manga_url: str
    manga_name: str
    manga_cover_url: str

    # Chapter
    chapter_id: UUID
    chapter_url: str
    chapter_title: str
    chapter_num: str

    class Config:
        from_attributes = True


# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/search")
async def search_manga(
    session: SessionDep,
    query: Optional[str] = "%20",
    page: int = Query(1, ge=1),
    sort: SortType = Query("recently_updated"),
) -> list[MangaInfo]:
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    query_clean = query.strip()

    try:
        natsu = NatsuExtractor(session)
        results = natsu.search(query=query_clean, page=page, sort=sort)
        print(results)
        return results
    except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"error: {str(e)}"
                ),
            )


# ── Chapter list ──────────────────────────────────────────────────────────────

@router.get("/chapter_list")
async def get_chapter_list(
    session: SessionDep,
    manga_url: str,
) -> list[ChapterInfo]:
    if not manga_url:
        raise HTTPException(status_code=400, detail="manga_url is required")

    try:
        natsu = NatsuExtractor(session)
        return natsu.get_chapter_list(manga_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Read (page images) ────────────────────────────────────────────────────────

@router.get("/read")
async def get_images(
    session: SessionDep,
    chapter_url: str,
) -> list[str]:
    if not chapter_url:
        raise HTTPException(status_code=400, detail="chapter_url is required")

    try:
        natsu = NatsuExtractor(session)
        return natsu.get_page_images(chapter_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── History ───────────────────────────────────────────────────────────────────

@router.post("/history/upsert", response_model=ReadHistoryResponse)
async def update_history(
    data: ReadHistoryUpdate,
    session: SessionDep,
    user_id: CurrentUser,
):
    """
    Upsert a reading-progress record.

    The client sends URLs (which it already has); this route resolves or
    creates the corresponding Manga and Chapter rows, then delegates to
    the query layer which works purely with UUIDs.
    """
    try:
        print(data)
        manga = get_manga_with_url(session,data.manga_url)
        chapter = get_or_create_chapter(
            session,
            chapter_url=data.chapter_url,
            title=data.chapter_title or "",
            num=data.chapter_num or "",
        )

        history = upsert_read_history_query(
            session=session,
            user_id=user_id,
            manga_id=manga.id,
            chapter_id=chapter.id,
            current_page=data.current_page,
        )

        return ReadHistoryResponse(
            id=history.id,
            user_id=history.user_id,
            current_page=history.current_page,
            updated_at=history.updated_at,
            manga_id=manga.id,
            manga_url=manga.manga_url,
            manga_name=manga.name,
            manga_cover_url=manga.manga_cover_url,
            chapter_id=chapter.id,
            chapter_url=chapter.link,
            chapter_title=chapter.title,
            chapter_num=chapter.num,
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{user_id}", response_model=list[ReadHistoryResponse])
async def read_user_history(user_id: CurrentUser, session: SessionDep):
    """
    Returns the user's reading history, enriched with manga name/cover
    and chapter title/num — most recently updated first.
    """
    rows = get_read_histories(session, user_id)
    return [
        ReadHistoryResponse(
            id=row.id,
            user_id=row.user_id,
            current_page=row.current_page,
            updated_at=row.updated_at,
            manga_id=row.manga_id,
            manga_url=row.manga_url,
            manga_name=row.manga_name,
            manga_cover_url=row.manga_cover_url,
            chapter_id=row.chapter_id,
            chapter_url=row.chapter_url,
            chapter_title=row.chapter_title,
            chapter_num=row.chapter_num,
        )
        for row in rows
    ]


# ── OCR ───────────────────────────────────────────────────────────────────────

@router.get("/ocr_data")
async def get_ocr_data(
    session: SessionDep,
    chapter_url: str,
) -> OCRResponse:
    if not chapter_url:
        raise HTTPException(status_code=400, detail="chapter_url is required")

    try:
        data = await do_ocr(session, chapter_url)
        return OCRResponse(pages=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/ocr_data/stream")
async def get_ocr_data_stream(
    session: SessionDep,
    chapter_url: str,
):
    if not chapter_url:
        raise HTTPException(status_code=400, detail="chapter_url is required")

    async def event_generator():
        try:
            async for page in do_ocr_stream(session, chapter_url):
                yield f"data: {json.dumps(page)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables buffering in nginx
        },
    )