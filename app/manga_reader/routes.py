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


@router.get("/manga", response_model=list[MangaPreview])
async def list_manga(
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    session = get_db_session()
    return _container.manga_reader_service.get_manga_list(session, query=q, limit=limit, offset=offset)


@router.get("/manga/{manga_id}", response_model=MangaDetail)
async def get_manga(
    manga_id: UUID,
):
    session = get_db_session()
    result = _container.manga_reader_service.get_manga_detail(session, manga_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manga not found")
    return result


@router.get("/read/{chapter_id}", response_model=ReadResponse)
async def read_chapter(
    chapter_id: UUID,
):
    session = get_db_session()
    result = _container.manga_reader_service.read_chapter(session, chapter_id)
    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return result


@router.get("/ocr/{chapter_id}", response_model=OCRResultResponse)
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


@router.get("/ocr/stream/{chapter_id}")
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


@router.get("/history", response_model=list[ReadHistoryResponse])
async def get_history(
    user: CurrentUser,
):
    session = get_db_session()
    return _container.manga_reader_service.get_history(session, user)


@router.post("/history", response_model=ReadHistoryResponse)
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


@router.delete("/history/{history_id}")
async def delete_history_by_id(
    history_id: UUID,
    user: CurrentUser,
):
    session = get_db_session()
    _container.manga_reader_service.delete_history(session, user, history_id)
    return {"success": True}