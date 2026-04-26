from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Annotated, Optional, List
from uuid import UUID
import json
from sqlmodel import select
from ..database import SessionDep, engine, Transcript, TranscriptStatus
from ..database import (
    check_exist_and_create_transcription_entry,
    get_transcript_by_resource,
    get_user_history,
    remove_history_entry,
    to_info,
)
from .schema import (
    TranscriptInfoResponse,
    TranscriptStatusResponse,
    TranscriptResult,
    TranscriptRequestResponse,
    YoutubeTranscriptRequestForm,
    UserHistoryListResponse,
    RemoveHistoryRequest
)
from ..security.auth import CurrentUser
from .transcribe_pipeline import transcribe_upload

router = APIRouter(tags=["Transcription"])


# ── List public transcripts (paginated) ───────────────────────────────────────

@router.get("/transcribe", response_model=List[TranscriptInfoResponse])
async def list_public_transcripts(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
):
    results = session.exec(
        select(Transcript)
        .where(Transcript.public == True)
        .order_by(Transcript.date_created.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [to_info(t) for t in results]

# ── Status & Info ─────────────────────────────────────────────────────────────

def _to_status(t: Transcript) -> TranscriptStatusResponse:
    return TranscriptStatusResponse(
        done=t.status == TranscriptStatus.Finish.value,
        msg=TranscriptStatus(t.status).name,
    )

@router.post("/transcribe/status")
async def batch_status(ids: List[UUID], session: SessionDep):
    return {
        str(id): _to_status(t) if (t := session.get(Transcript, id)) else None
        for id in ids
    }

@router.get("/transcribe/{id}/info", response_model=Optional[TranscriptInfoResponse])
async def get_info(id: UUID, session: SessionDep):
    t = session.get(Transcript, id)
    return to_info(t) if t else None

@router.get("/transcribe/{id}/data", response_model=Optional[TranscriptResult])
async def get_data(id: UUID, session: SessionDep):
    t = session.get(Transcript, id)
    if not t or not t.data:
        return None
    return TranscriptResult(**json.loads(t.data))

# ── Submit jobs (Authenticated) ───────────────────────────────────────────────

def _bg_transcribe(form: YoutubeTranscriptRequestForm,user_id : UUID):
    from sqlmodel import Session
    with Session(engine) as session:
        transcribe_upload(session, form,user_id)

@router.post("/transcribe/youtube", response_model=TranscriptRequestResponse)
async def transcribe_from_site(
    form: YoutubeTranscriptRequestForm, # Passed as JSON body
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
    session: SessionDep,
):
    # Overwrite form user_id with the one from the JWT
    info = check_exist_and_create_transcription_entry(session, form,user_id)
    
    if info.status == TranscriptStatus.InQueue.value:
        background_tasks.add_task(_bg_transcribe, form,user_id)
        
    return TranscriptRequestResponse(transcript_id=info.id, success=True)

# ── History (Authenticated) ───────────────────────────────────────────────────

@router.get("/history", response_model=UserHistoryListResponse)
async def get_transcription_history(
    user_id: CurrentUser,
    session: SessionDep
) -> UserHistoryListResponse:
    """Returns the authenticated user's transcription history."""
    return get_user_history(session, user_id)

@router.delete("/history")
async def delete_history_entry(
    req: RemoveHistoryRequest,
    user_id: CurrentUser,
    session: SessionDep
):
    """Removes an entry from history. Only if owned by user."""
    success = remove_history_entry(session, req.history_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="History entry not found or unauthorized")
    return {"success": True}