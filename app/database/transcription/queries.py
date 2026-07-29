from .schema import *
from sqlmodel import Session, SQLModel, create_engine, select
import json
from uuid import UUID
from datetime import datetime, timezone


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
    session: Session, form: YoutubeTranscriptRequestForm,user_id: UUID
) -> TranscriptInfoResponse:
    """
    Idempotent: if resource exists, link to user history if not already linked.
    Otherwise, create Transcript and history entry.
    Also updates existing visited video history entries with transcript_id.
    """
    transcript = None

    # 1. Check if the transcript already exists in the system
    if form.resource_id:
        transcript = get_transcript_by_resource(session, form.resource_id, form.original_source)

    # 2. If it doesn't exist, create it
    if not transcript:
        transcript = Transcript(
            name=form.name,
            resource_url=form.resource_url,
            resource_id=form.resource_id,
            thumnail_url=form.thumbnail_url,
            original_source=form.original_source,
            status=TranscriptStatus.InQueue.value,
            public=form.public,
        )
        session.add(transcript)
        session.flush()  # Ensure transcript.id is available

    # 3. Check if this user has a history entry for this video (visited but not transcribed)
    history_entry = session.exec(
        select(TranscriptionHistory).where(
            TranscriptionHistory.user_id == user_id,
            TranscriptionHistory.resource_id == form.resource_id,
        )
    ).first()

    # 4. If history exists but transcript_id is NULL, update it with the transcript_id
    if history_entry and history_entry.transcript_id is None:
        history_entry.transcript_id = transcript.id
        session.add(history_entry)
        session.commit()
    elif not history_entry:
        # 5. If no history entry exists, create one
        history_entry = TranscriptionHistory(
            user_id=user_id,
            transcript_id=transcript.id,
            resource_id=form.resource_id,
            name=form.name,
            thumbnail_url=form.thumbnail_url,
            original_source=form.original_source,
            resource_url=form.resource_url,
        )
        session.add(history_entry)
        session.commit()

    session.refresh(transcript)
    return to_info(transcript)


def get_user_history(session: Session, user_id: UUID) -> UserHistoryListResponse:
    """
    Returns user's history including both transcribed videos and visited videos.
    Transcribed videos have transcript_id set, visited videos have transcript_id=NULL.
    """
    history_statement = (
        select(TranscriptionHistory, Transcript)
        .outerjoin(Transcript, TranscriptionHistory.transcript_id == Transcript.id)
        .where(TranscriptionHistory.user_id == user_id)
        .order_by(TranscriptionHistory.date_created.desc())
    )
    results = session.exec(history_statement).all()
    
    history_items = []
    for h, t in results:
        if t:
            history_items.append(UserHistoryResponse(
                history_id=h.id,
                transcript_id=t.id,
                name=t.name,
                thumbnail_url=t.thumnail_url,
                original_source=t.original_source,
                date_created=h.date_created,
                status=t.status,
                is_transcribed=True,
            ))
        else:
            history_items.append(UserHistoryResponse(
                history_id=h.id,
                transcript_id=None,
                name=h.name,
                thumbnail_url=h.thumbnail_url,
                original_source=h.original_source,
                date_created=h.date_created,
                status=None,
                is_transcribed=False,
            ))
    
    return UserHistoryListResponse(items=history_items, total=len(history_items))


def remove_history_entry(session: Session, history_id: UUID, user_id: UUID) -> bool:
    """
    Removes a specific entry from a user's history. 
    Requires user_id to ensure ownership before deletion.
    """
    history_entry = session.exec(
        select(TranscriptionHistory).where(
            TranscriptionHistory.id == history_id, 
            TranscriptionHistory.user_id == user_id
        )
    ).one_or_none()
    
    if not history_entry:
        return False
    
    session.delete(history_entry)
    session.commit()
    return True


def get_orphaned_transcriptions(session: Session):
    stmt = select(Transcript).where(
        Transcript.status == TranscriptStatus.Transcripting.value,
    )

    results = session.exec(stmt).all()
    return results


# ── Video Progress Queries ─────────────────────────────────────────────────

def get_video_progress(
    session: Session, user_id: UUID, resource_id: str, original_source: str
) -> VideoProgress | None:
    return session.exec(
        select(VideoProgress).where(
            VideoProgress.user_id == user_id,
            VideoProgress.resource_id == resource_id,
            VideoProgress.original_source == original_source,
        )
    ).first()


def save_video_progress(
    session: Session,
    user_id: UUID,
    resource_id: str,
    original_source: str,
    current_page: int,
) -> VideoProgress:
    progress = get_video_progress(session, user_id, resource_id, original_source)
    if not progress:
        progress = VideoProgress(
            user_id=user_id,
            resource_id=resource_id,
            original_source=original_source,
            current_page=current_page,
        )
        session.add(progress)
    else:
        progress.current_page = current_page
        progress.updated_at = datetime.now(timezone.utc)
        session.add(progress)
    session.commit()
    session.refresh(progress)
    return progress