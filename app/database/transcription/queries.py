
from .schema import *
from sqlmodel import Session, SQLModel, create_engine, select
import json
from uuid import UUID



def to_info(t: Transcript) -> TranscriptInfoResponse:
    return TranscriptInfoResponse(
        id=t.id,
        original_source=t.original_source,
        thumnail_url=t.thumnail_url,
        resource_url=t.resource_url,
        resource_id=t.resource_id,
        status=t.status,
    )


# ── Transcript queries ────────────────────────────────────────────────────────

def get_transcript_by_resource(
    session: Session, resource_id: str, original_source: str
) -> Transcript | None:
    return session.exec(
        select(Transcript).where(
            Transcript.resource_id == resource_id,
            Transcript.original_source == original_source,
        )
    ).first()


def get_transcript_info(session: Session, id: UUID) -> TranscriptInfoResponse | None:
    t = session.get(Transcript, id)
    return to_info(t) if t else None


def check_status_by_id(session: Session, id: UUID) -> int | None:
    t = session.get(Transcript, id)
    return t.status if t else None


def check_status_by_resource(
    session: Session, resource_id: str, original_source: str
) -> int | None:
    t = get_transcript_by_resource(session, resource_id, original_source)
    return t.status if t else None


def save_transcript(session: Session, id: UUID, data: dict) -> bool:
    t = session.get(Transcript, id)
    if not t:
        return False
    t.data = json.dumps(data)
    session.add(t)
    session.commit()
    return True


def update_status(session: Session, id: UUID, status: int) -> Transcript:
    t = session.get(Transcript, id)
    if not t:
        raise ValueError(f"Transcript {id} not found")
    t.status = status
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


# ── Queue — DB-backed via Transcript.status ───────────────────────────────────

def claim_next_queued(session: Session) -> Transcript | None:
    """
    Pull the oldest InQueue transcript and atomically mark it as Transcripting.
    Returns None if nothing is queued.
    """
    t = session.exec(
        select(Transcript)
        .where(Transcript.status == TranscriptStatus.InQueue.value)
        .order_by(Transcript.date_created)
        .limit(1)
    ).first()

    if not t:
        return None

    t.status = TranscriptStatus.Transcripting.value
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def check_exist_and_create_transcription_entry(
    session: Session, form: YoutubeTranscriptRequestForm
) -> TranscriptInfoResponse:
    """
    Idempotent: if this resource was already submitted return its info.
    Otherwise create a Transcript with status=InQueue and return info.
    """

    if form.resource_id:
        existing = get_transcript_by_resource(session, form.resource_id, form.original_source)
        if existing:
            return to_info(existing)

    instance = Transcript(
        name=form.name,
        resource_url=form.resource_url,
        resource_id=form.resource_id,
        thumnail_url=form.thumbnail_url,
        original_source=form.original_source,
        status=TranscriptStatus.InQueue.value,
        public=form.public,
    )
    session.add(instance)
    session.commit()
    session.refresh(instance)
    return to_info(instance)
