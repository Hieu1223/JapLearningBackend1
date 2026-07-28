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
)
from ..security.auth import CurrentUser
from .transcribe_pipeline import transcribe_upload

router = APIRouter(tags=["Transcription"])


@router.get("/transcribe/{id}/detail", response_model=TranscriptDetailResponse)
async def get_transcription_detail(
    id: UUID,
    session: SessionDep,
):
    t = session.get(Transcript, id)
    if not t:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    done = t.status == TranscriptStatus.Finish.value
    msg = TranscriptStatus(t.status).name
    
    data = None
    if done and t.data:
        data = TranscriptResult(**json.loads(t.data))
    
    return TranscriptDetailResponse(
        id=t.id,
        original_source=t.original_source,
        thumnail_url=t.thumnail_url,
        resource_url=t.resource_url,
        resource_id=t.resource_id,
        status=t.status,
        done=done,
        msg=msg,
        data=data,
    )


@router.post("/transcribe/{id}/rerun", response_model=TranscriptRequestResponse)
async def rerun_transcription(
    id: UUID,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
    session: SessionDep,
):
    t = session.get(Transcript, id)
    if not t:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    t.status = TranscriptStatus.InQueue.value
    session.add(t)
    session.commit()
    session.refresh(t)
    
    form = YoutubeTranscriptRequestForm(
        name=t.name,
        resource_id=t.resource_id,
        original_source=t.original_source,
        public=t.public,
        thumbnail_url=t.thumnail_url,
        resource_url=t.resource_url,
    )
    
    background_tasks.add_task(_bg_transcribe, form, user_id)
    
    return TranscriptRequestResponse(transcript_id=id, success=True)


def _bg_transcribe(form: YoutubeTranscriptRequestForm, user_id: UUID):
    from sqlmodel import Session
    with Session(engine) as session:
        transcribe_upload(session, form, user_id)


@router.post("/transcribe/youtube", response_model=TranscriptRequestResponse)
async def transcribe_from_site(
    form: YoutubeTranscriptRequestForm,
    user_id: CurrentUser,
    background_tasks: BackgroundTasks,
    session: SessionDep,
):
    info = check_exist_and_create_transcription_entry(session, form, user_id)
    
    if info.status == TranscriptStatus.InQueue.value:
        background_tasks.add_task(_bg_transcribe, form, user_id)
    
    return TranscriptRequestResponse(transcript_id=info.id, success=True)


@router.post("/visit", response_model=TranscriptDetailResponse)
async def visit_video(
    form: YoutubeTranscriptRequestForm,
    user_id: CurrentUser,
    session: SessionDep,
):
    from ..database.transcription.schema import TranscriptionHistory
    
    existing = session.exec(
        select(TranscriptionHistory).where(
            TranscriptionHistory.user_id == user_id,
            TranscriptionHistory.resource_id == form.resource_id,
        )
    ).first()
    
    if existing:
        existing.date_created = datetime.now(timezone.utc)
        session.add(existing)
        session.commit()
        session.refresh(existing)
    else:
        history_entry = TranscriptionHistory(
            user_id=user_id,
            resource_id=form.resource_id,
            name=form.name,
            thumbnail_url=form.thumbnail_url,
            original_source=form.original_source,
            resource_url=form.resource_url,
        )
        session.add(history_entry)
        session.commit()
        session.refresh(history_entry)
    
    t = session.get(Transcript, existing.transcript_id) if existing.transcript_id else None
    
    done = False
    msg = "NotTranscribed"
    data = None
    
    if t:
        done = t.status == TranscriptStatus.Finish.value
        msg = TranscriptStatus(t.status).name
        if done and t.data:
            data = TranscriptResult(**json.loads(t.data))
    
    return TranscriptDetailResponse(
        id=t.id if t else existing.id,
        original_source=existing.original_source,
        thumnail_url=existing.thumbnail_url,
        resource_url=existing.resource_url,
        resource_id=existing.resource_id,
        status=t.status if t else 0,
        done=done,
        msg=msg,
        data=data,
    )


@router.get("/history", response_model=UserHistoryListResponse)
async def get_transcription_history(
    user_id: CurrentUser,
    session: SessionDep
) -> UserHistoryListResponse:
    return get_user_history(session, user_id)


@router.delete("/history")
async def delete_history_entry(
    req: RemoveHistoryRequest,
    user_id: CurrentUser,
    session: SessionDep
):
    success = remove_history_entry(session, req.history_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="History entry not found or unauthorized")
    return {"success": True}