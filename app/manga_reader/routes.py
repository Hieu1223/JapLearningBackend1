import json
import os
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional
from uuid import UUID

from ..security.auth import CurrentUser
from ..container import Container, get_db_session
from .schema import (
    MangaPreview,
    MangaDetail,
    ReadResponse,
    OCRResultResponse,
    ReadHistoryUpdate,
    ReadHistoryResponse,
)

router = APIRouter(tags=["Manga"])

_container = Container()

TAGS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "asset", "tags.json"
)

try:
    with open(TAGS_FILE, "r", encoding="utf-8") as _f:
        _ALL_TAGS = json.load(_f).get("tags", [])
except (FileNotFoundError, json.JSONDecodeError):
    _ALL_TAGS = []


def _order_tags(tags: list[str], order_by: Optional[str]) -> list[str]:
    desc = order_by.startswith("-") if order_by else False
    key = order_by[1:] if desc else order_by
    if key in ("az", "name", "title", None):
        return sorted(tags, reverse=desc)
    if key in ("len", "length"):
        return sorted(tags, key=len, reverse=desc)
    return sorted(tags, reverse=desc)


@router.get("/manga", response_model=list[MangaPreview], tags=["Manga"], description="List manga with optional text search, genre tag filter and pagination")
async def list_manga(
    q: Optional[str] = Query(default=None),
    tags: Optional[list[str]] = Query(default=None, description="Filter by one or more genres"),
    order_by: Optional[str] = Query(
        default=None,
        description="Sort order: latest (newest update), -latest (oldest update), az (A-Z title), -az (Z-A title), created (oldest first), -created (newest first)",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    session = get_db_session()
    return _container.manga_reader_service.get_manga_list(
        session,
        query=q,
        limit=limit,
        offset=offset,
        tags=tags,
        order_by=order_by,
    )


@router.get("/tags", response_model=list[str], tags=["Manga"], description="List all available manga genre tags with optional prefix search, ordering and pagination")
async def list_tags(
    q: Optional[str] = Query(default=None, description="Case-insensitive prefix filter on tag name"),
    order_by: Optional[str] = Query(
        default=None,
        description="Sort order: az (A-Z), -az (Z-A), len (shortest first), -len (longest first)",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    tags = _ALL_TAGS
    if q:
        q_lower = q.lower()
        tags = [t for t in tags if t.lower().startswith(q_lower)]
    tags = _order_tags(tags, order_by)
    return tags[offset:offset + limit]


@router.get("/manga/{manga_id}", response_model=MangaDetail, tags=["Manga"], description="Fetch the full metadata and chapter list for a single manga")
async def get_manga(
    manga_id: UUID,
):
    session = get_db_session()
    result = _container.manga_reader_service.get_manga_detail(session, manga_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manga not found")
    return result


@router.get("/read/{chapter_id}", response_model=ReadResponse, tags=["Manga"], description="Load the readable pages and navigation info for a single chapter")
async def read_chapter(
    chapter_id: UUID,
):
    session = get_db_session()
    result = _container.manga_reader_service.read_chapter(session, chapter_id)
    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return result


@router.get("/ocr/{chapter_id}", response_model=OCRResultResponse, tags=["Manga"], description="Return a previously computed OCR result for a chapter")
async def get_ocr(
    chapter_id: UUID,
    user: CurrentUser,
):
    session = get_db_session()
    result = _container.manga_reader_service.get_existing_ocr(session, chapter_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No OCR result found. Use /ocr/stream/{chapter_id} to run OCR.",
        )
    return result


@router.get("/ocr/stream/{chapter_id}", tags=["Manga"], description="Stream OCR extraction progress for a chapter as server-sent events, persisting the result when complete")
async def stream_ocr(
    chapter_id: UUID,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    session = get_db_session()
    if _container.manga_reader_service.get_existing_ocr(session, chapter_id):
        raise HTTPException(
            status_code=409,
            detail="Chapter already OCR'd. Fetch the result via GET /ocr/{chapter_id}.",
        )

    try:
        return StreamingResponse(
            _container.manga_reader_service.stream_ocr(session, chapter_id, user, background_tasks),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/history", response_model=list[ReadHistoryResponse], tags=["Manga"], description="Return the current user's manga reading history")
async def get_history(
    user: CurrentUser,
):
    session = get_db_session()
    return _container.manga_reader_service.get_history(session, user)


@router.post("/history", response_model=ReadHistoryResponse, tags=["Manga"], description="Create or update the user's reading progress for a manga chapter")
async def upsert_history(
    data: ReadHistoryUpdate,
    user: CurrentUser,
):
    session = get_db_session()
    try:
        return _container.manga_reader_service.upsert_history(
            session,
            user_id=user,
            manga_id=data.manga_id,
            chapter_id=data.chapter_id,
            current_page=data.current_page,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/history/{history_id}", tags=["Manga"], description="Delete a single reading-history entry by its id")
async def delete_history_by_id(
    history_id: UUID,
    user: CurrentUser,
):
    session = get_db_session()
    result = _container.manga_reader_service.delete_history_by_id(session, user, history_id)
    if not result:
        raise HTTPException(status_code=404, detail="History not found")
    return {"success": True}


@router.delete("/history/manga/{manga_id}", tags=["Manga"], description="Delete all reading-history entries for a given manga")
async def delete_history_by_manga(
    manga_id: UUID,
    user: CurrentUser,
):
    session = get_db_session()
    result = _container.manga_reader_service.delete_history(session, user, manga_id)
    if not result:
        raise HTTPException(status_code=404, detail="History not found")
    return {"success": True}


@router.delete("/ocr/{chapter_id}", tags=["Manga"], description="Clear a chapter's stored OCR result so it can be re-run")
async def reset_ocr(
    chapter_id: UUID,
    user: CurrentUser,
):
    session = get_db_session()
    result = _container.manga_reader_service.reset_ocr(session, chapter_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No OCR result found for this chapter.",
        )
    return {"success": True}