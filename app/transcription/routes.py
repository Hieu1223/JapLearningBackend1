from fastapi import APIRouter, HTTPException, BackgroundTasks
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import select
from ..database import SessionDep, engine, Transcript, TranscriptStatus
from ..database import (
    check_exist_and_create_transcription_entry,
    get_user_history,
    remove_history_entry,
)
from .schema import (
    TranscriptResult,
    TranscriptRequestResponse,
    YoutubeTranscriptRequestForm,
    UserHistoryListResponse,
    RemoveHistoryRequest,
    TranscriptDetailResponse,
    VideoProgressResponse,
    SaveVideoProgressRequest,
)
from ..security.auth import CurrentUser
from ..container import Container, get_db_session
from .transcribe_pipeline import transcribe_upload

router = APIRouter(tags=["Transcription"])

_container = Container()


@router.get("/transcribe/{id}/detail", response_model=TranscriptDetailResponse)
async def get_transcription_detail(
    id: UUID,
):
    session = get_db_session()
    return _container.transcription_service.get_transcription_detail(session, id)


@router.post("/transcribe/{id}/rerun", response_model=TranscriptRequestResponse)
async def rerun_transcription(
    id: UUID,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
):
    session = get_db_session()
    return _container.transcription_service.rerun_transcription(
        session, id, user_id, background_tasks
    )


@router.post("/transcribe/youtube", response_model=TranscriptRequestResponse)
async def transcribe_from_site(
    form: YoutubeTranscriptRequestForm,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
):
    session = get_db_session()
    return _container.transcription_service.submit_transcription(
        session, form, user_id, background_tasks
    )


@router.post("/visit", response_model=TranscriptDetailResponse)
async def visit_video(
    form: YoutubeTranscriptRequestForm,
    user_id: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.visit_video(session, form, user_id)


@router.get("/history", response_model=UserHistoryListResponse)
async def get_transcription_history(
    user_id: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.get_history(session, user_id)


@router.delete("/history")
async def delete_history_entry(
    req: RemoveHistoryRequest,
    user_id: CurrentUser,
):
    session = get_db_session()
    success = _container.transcription_service.delete_history_entry(
        session, req.history_id, user_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="History entry not found or unauthorized")
    return {"success": True}


# ── Video Progress ─────────────────────────────────────────────────────────────

@router.get("/progress", response_model=VideoProgressResponse | None)
async def get_video_progress(
    resource_id: str,
    original_source: str = "Youtube",
    user: CurrentUser = None,
):
    session = get_db_session()
    return _container.transcription_service.get_video_progress(
        session, user, resource_id, original_source
    )


@router.post("/progress", response_model=VideoProgressResponse)
async def save_video_progress(
    req: SaveVideoProgressRequest,
    user: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.save_video_progress(
        session, user, req.resource_id, req.original_source, req.current_page
    )