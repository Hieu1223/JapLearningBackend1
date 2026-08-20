from fastapi import APIRouter, HTTPException, BackgroundTasks
from uuid import UUID
from typing import Optional
from ...security.auth import CurrentUser
from ...container import Container, get_db_session
from ..schemas.transcription_request import (
    SubmitTranscriptionRequest,
    TranscriptionJobResponse,
    TranscriptionListResponse,
    VisitedVideoListResponse,
)
from ...database.transcription.schema import TranscriptDetailResponse

router = APIRouter(tags=["Transcription"])

_container = Container()


@router.post("", response_model=TranscriptionJobResponse, tags=["Transcription"], description="Submit a transcription job for an already-previewed video by its video_id; the job is processed in the background")
async def submit_transcription_job(
    req: SubmitTranscriptionRequest,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    session = get_db_session()
    return _container.transcription_service.submit_job(
        session, req.video_id, user, background_tasks
    )


@router.get("", response_model=TranscriptionListResponse, tags=["Transcription"], description="List the transcription attempts for a specific video, with their current status")
async def list_transcriptions(
    video_id: UUID,
    limit: int = 100,
    offset: int = 0,
):
    session = get_db_session()
    return _container.transcription_service.list_transcriptions(session, video_id, limit, offset)


@router.get("/visited", response_model=VisitedVideoListResponse, tags=["Transcription"], description="List the current user's visited videos (derived from saved playback progress)")
async def list_visited_videos(
    user: CurrentUser,
):
    session = get_db_session()
    return _container.transcription_service.get_visited_videos(session, user)


@router.get("/{transcript_id}", response_model=TranscriptDetailResponse, tags=["Transcription"], description="Poll a transcription job by id; returns status, and the full transcript once finished")
async def poll_transcription(
    transcript_id: UUID,
):
    session = get_db_session()
    try:
        return _container.transcription_service.poll_transcription(session, transcript_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
