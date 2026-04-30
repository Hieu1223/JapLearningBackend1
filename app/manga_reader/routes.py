from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional
from uuid import UUID

from ..database import SessionDep
from ..security.auth import CurrentUser
from .schema import (
    MangaPreview,
    MangaDetail,
    ReadResponse,
    OCRResultResponse,
    ReadHistoryUpdate,
    ReadHistoryResponse,
)
from .controller import (
    ctrl_get_manga_list,
    ctrl_get_manga_detail,
    ctrl_read_chapter,
    ctrl_get_existing_ocr,
    ctrl_stream_ocr,
    ctrl_get_history,
    ctrl_upsert_history,
)

router = APIRouter(tags=["Manga"])


# ─────────────────────────────────────────────────────────────
# MANGA LIST / SEARCH
# ─────────────────────────────────────────────────────────────

@router.get("/manga", response_model=list[MangaPreview])
async def list_manga(
    session: SessionDep,
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return ctrl_get_manga_list(session, query=q, limit=limit, offset=offset)


# ─────────────────────────────────────────────────────────────
# AGGREGATE MANGA (detail + chapter list)
# ─────────────────────────────────────────────────────────────

@router.get("/manga/{manga_id}", response_model=MangaDetail)
async def get_manga(
    manga_id: UUID,
    session: SessionDep,
):
    result = ctrl_get_manga_detail(session, manga_id)
    if not result:
        raise HTTPException(status_code=404, detail="Manga not found")
    return result


# ─────────────────────────────────────────────────────────────
# READ CHAPTER
# ─────────────────────────────────────────────────────────────

@router.get("/read/{chapter_id}", response_model=ReadResponse)
async def read_chapter(
    chapter_id: UUID,
    session: SessionDep,
):
    result = ctrl_read_chapter(session, chapter_id)
    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return result


# ─────────────────────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────────────────────

@router.get("/ocr/{chapter_id}", response_model=OCRResultResponse)
async def get_ocr(
    chapter_id: UUID,
    session: SessionDep,
    user: CurrentUser,
):
    result = ctrl_get_existing_ocr(session, chapter_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No OCR result found. Use /ocr/stream/{chapter_id} to run OCR.",
        )
    return result


@router.get("/ocr/stream/{chapter_id}")
async def stream_ocr(
    chapter_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    if ctrl_get_existing_ocr(session, chapter_id):
        raise HTTPException(
            status_code=409,
            detail="Chapter already OCR'd. Fetch the result via GET /ocr/{chapter_id}.",
        )

    try:
        return StreamingResponse(
            ctrl_stream_ocr(session, chapter_id, user, background_tasks),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ─────────────────────────────────────────────────────────────
# HISTORY
# ─────────────────────────────────────────────────────────────

@router.get("/history", response_model=list[ReadHistoryResponse])
async def get_history(
    session: SessionDep,
    user: CurrentUser,
):
    return ctrl_get_history(session, user)


@router.post("/history", response_model=ReadHistoryResponse)
async def upsert_history(
    data: ReadHistoryUpdate,
    session: SessionDep,
    user: CurrentUser,
):
    try:
        return ctrl_upsert_history(
            session,
            user_id=user,
            manga_id=data.manga_id,
            chapter_id=data.chapter_id,
            current_page=data.current_page,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))