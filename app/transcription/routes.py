from typing import Annotated
from uuid import UUID
from pydantic import BaseModel
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlmodel import Session, select
from .schema import (
    Transcript,
    TranscriptRequestResponse,
    TranscriptInfoResponse,
    TranscriptStatusResponse,
    TranscriptResult,
    TranscriptStatus,
    YoutubeTranscriptRequestForm
)
from .transcribe_pipeline import transcribe_upload
from .db import (
    SessionDep, engine,
    check_exist_and_create_transcription_entry,
    get_transcript_by_resource,
    to_info,
)
import json

router = APIRouter(tags=["transcription"])


# ── List public transcripts (paginated) ───────────────────────────────────────

@router.get("/transcribe")
async def list_public_transcripts(
    session: SessionDep,
    page: int = 1,
    page_size: int = 20,
) -> list[TranscriptInfoResponse]:
    """Returns a paginated list of all public transcripts, newest first."""
    results = session.exec(
        select(Transcript)
        .where(Transcript.public == True)
        .order_by(Transcript.date_created.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [to_info(t) for t in results]


# ── Status only ───────────────────────────────────────────────────────────────

def _to_status(t: Transcript) -> TranscriptStatusResponse:
    return TranscriptStatusResponse(
        done=t.status == TranscriptStatus.Finish.value,
        msg=TranscriptStatus(t.status).name,
    )


@router.post("/transcribe/status")
async def batch_status(
    ids: list[UUID],
    session: SessionDep,
) -> dict[str, TranscriptStatusResponse | None]:
    """Returns only the status for each transcript ID."""
    return {
        str(id): _to_status(t) if (t := session.get(Transcript, id)) else None
        for id in ids
    }


class ResourceQuery(BaseModel):
    resource_id: str
    original_source: str


@router.post("/transcribe/status/resource")
async def batch_status_by_resource(
    resources: list[ResourceQuery],
    session: SessionDep,
) -> dict[str, TranscriptStatusResponse | None]:
    """Returns only the status for each {resource_id, original_source} pair."""
    return {
        r.resource_id: _to_status(t) if (t := get_transcript_by_resource(session, r.resource_id, r.original_source)) else None
        for r in resources
    }


# ── Info ──────────────────────────────────────────────────────────────────────

@router.get("/transcribe/{id}/info")
async def get_info(
    id: UUID,
    session: SessionDep,
) -> TranscriptInfoResponse | None:
    """Returns full transcript metadata by ID."""
    t = session.get(Transcript, id)
    return to_info(t) if t else None


@router.get("/transcribe/resource/{original_source}/{resource_id}/info")
async def get_info_by_resource(
    resource_id: str,
    original_source: str,
    session: SessionDep,
) -> TranscriptInfoResponse | None:
    """Returns full transcript metadata by resource_id and source site."""
    t = get_transcript_by_resource(session, resource_id, original_source)
    return to_info(t) if t else None


# ── Transcript data ───────────────────────────────────────────────────────────

@router.get("/transcribe/{id}/data")
async def get_data(
    id: UUID,
    session: SessionDep,
) -> TranscriptResult | None:
    """Returns transcript result data by ID."""
    t = session.get(Transcript, id)
    if not t or not t.data:
        return None
    return TranscriptResult(**json.loads(t.data))


@router.get("/transcribe/resource/{original_source}/{resource_id}/data")
async def get_data_by_resource(
    resource_id: str,
    original_source: str,
    session: SessionDep,
) -> TranscriptResult | None:
    """Returns transcript result data by resource_id and source site."""
    t = get_transcript_by_resource(session, resource_id, original_source)
    if not t or not t.data:
        return None
    return TranscriptResult(**json.loads(t.data))


# ── Background task runner ────────────────────────────────────────────────────

def _bg_transcribe(form: YoutubeTranscriptRequestForm):
    with Session(engine) as session:
        transcribe_upload(session, form)


# ── Submit jobs ───────────────────────────────────────────────────────────────

@router.post("/transcribe/youtube")
async def transcribe_from_site(
    form: Annotated[YoutubeTranscriptRequestForm, Depends()],
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> TranscriptRequestResponse:
    """Generic endpoint for any supported site (YouTube, etc.)"""
    info = check_exist_and_create_transcription_entry(session, form)
    if info.status == TranscriptStatus.InQueue.value:
        background_tasks.add_task(_bg_transcribe, form)
    return TranscriptRequestResponse(transcript_id=info.id, success=True)
