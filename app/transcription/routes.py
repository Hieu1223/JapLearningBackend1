from fastapi import APIRouter, HTTPException, BackgroundTasks
from uuid import UUID
from ..database import (
    check_exist_and_create_transcription_entry,
    get_user_history,
    remove_history_entry,
)
from ..database.transcription.schema import (
    TranscriptionHistory,
    TranscriptResult,
    TranscriptRequestResponse,
    YoutubeTranscriptRequestForm,
    UserHistoryListResponse,
    RemoveHistoryRequest,
    TranscriptDetailResponse,
    VideoProgressResponse,
    SaveVideoProgressRequest,
    SaveIndividualSettingsRequest,
)
from ..security.auth import CurrentUser
from ..container import Container, get_db_session
from .transcribe_pipeline import transcribe_upload

router = APIRouter(tags=["Transcription"])

_container = Container()


@router.get("/transcribe/{id}/detail", response_model=TranscriptDetailResponse, tags=["Transcription"], description="Fetch the full detail and transcript text for a single transcription by id")
async def get_transcription_detail(
    id: UUID,
):
    session = get_db_session()
    return _container.transcription_service.get_transcription_detail(session, id)


@router.post("/transcribe/{id}/settings", response_model=dict, tags=["Transcription"], description="Save per-transcription user settings, such as display and playback preferences")
async def save_individual_settings(
    id: UUID,
    req: SaveIndividualSettingsRequest,
    user_id: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.save_individual_settings(
        session, id, user_id, req.settings
    )


@router.post("/transcribe/{id}/rerun", response_model=TranscriptRequestResponse, tags=["Transcription"], description="Re-queue an existing transcription to be re-processed from its source in the background")
async def rerun_transcription(
    id: UUID,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
):
    session = get_db_session()
    return _container.transcription_service.rerun_transcription(
        session, id, user_id, background_tasks
    )


@router.post("/transcribe/youtube", response_model=TranscriptRequestResponse, tags=["Transcription"], description="Submit a YouTube URL for transcription; the job is processed in the background")
async def transcribe_from_site(
    form: YoutubeTranscriptRequestForm,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
):
    session = get_db_session()
    return _container.transcription_service.submit_transcription(
        session, form, user_id, background_tasks
    )


@router.post("/visit", response_model=TranscriptDetailResponse, tags=["Transcription"], description="Record a visit to a video and return any existing transcription detail for it")
async def visit_video(
    form: YoutubeTranscriptRequestForm,
    user_id: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.visit_video(session, form, user_id)


@router.get("/history", response_model=UserHistoryListResponse, tags=["Transcription"], description="Return the current user's list of transcription history entries")
async def get_transcription_history(
    user_id: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.get_history(session, user_id)


@router.delete("/history", tags=["Transcription"], description="Delete a single transcription history entry owned by the current user")
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

@router.get("/progress", response_model=VideoProgressResponse | None, tags=["Transcription"], description="Return the saved playback progress for a resource, if any")
async def get_video_progress(
    resource_id: str,
    original_source: str = "Youtube",
    user: CurrentUser = None,
):
    session = get_db_session()
    return _container.transcription_service.get_video_progress(
        session, user, resource_id, original_source
    )


@router.post("/progress", response_model=VideoProgressResponse, tags=["Transcription"], description="Save the current playback progress for a resource for the current user")
async def save_video_progress(
    req: SaveVideoProgressRequest,
    user: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.save_video_progress(
        session, user, req.resource_id, req.original_source, req.current_page
    )