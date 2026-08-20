from .schema import *
from sqlmodel import Session, SQLModel, create_engine, select
import json
from uuid import UUID
from datetime import datetime, timezone


def to_info(v: Video, t: Transcript | None = None) -> TranscriptInfoResponse:
    return TranscriptInfoResponse(
        id=t.id if t else v.id,
        video_id=v.id,
        original_source=v.original_source,
        thumbnail_url=v.thumbnail_url,
        resource_url=v.resource_url,
        resource_id=v.resource_id,
        name=v.name,
        status=t.status if t else v.status,
    )


# ── Video queries ──────────────────────────────────────────────────────────────

def get_video_by_resource(
    session: Session, resource_id: str, original_source: str
) -> Video | None:
    return session.exec(
        select(Video).where(
            Video.resource_id == resource_id,
            Video.original_source == original_source,
        )
    ).first()


def get_video_by_id(session: Session, video_id: UUID) -> Video | None:
    return session.get(Video, video_id)


def get_or_create_video_from_preview(
    session: Session,
    resource_id: str,
    name: str,
    thumbnail_url: str | None,
    resource_url: str,
    video_data: dict | None = None,
    original_source: str = "Youtube",
) -> Video:
    """Return the existing Video for a source resource, creating it on first preview.

    The full preview ``video_data`` is persisted on the Video row so the preview
    can be reconstructed without re-fetching YouTube. The DB ``id`` (a uuid,
    distinct from ``resource_id``) is what callers use for transcription jobs.
    """
    video = get_video_by_resource(session, resource_id, original_source)
    if not video:
        video = Video(
            original_source=original_source,
            resource_id=resource_id,
            resource_url=resource_url,
            thumbnail_url=thumbnail_url or "",
            name=name,
            status=0,  # Uploading / not transcribed yet
            public=True,
            individual_settings=json.dumps(video_data) if video_data is not None else None,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
    return video


# ── Transcript queries ────────────────────────────────────────────────────────

def get_transcript_by_id(session: Session, transcript_id: UUID) -> Transcript | None:
    return session.get(Transcript, transcript_id)


def get_latest_transcript_for_video(session: Session, video_id: UUID) -> Transcript | None:
    return session.exec(
        select(Transcript)
        .where(Transcript.video_id == video_id)
        .order_by(Transcript.transcript_date.desc())
        .limit(1)
    ).first()


def has_transcript_for_video(session: Session, video_id: UUID) -> bool:
    """Return True if a video has a finished (saved) transcript."""
    v = session.get(Video, video_id)
    if not v:
        return False
    if v.status != TranscriptStatus.Finish.value:
        return False
    return get_latest_transcript_for_video(session, video_id) is not None


def get_transcript_info(session: Session, id: UUID) -> TranscriptInfoResponse | None:
    t = session.get(Transcript, id)
    if not t:
        return None
    v = session.get(Video, t.video_id) if t.video_id else None
    return to_info(v, t) if v else None


def check_status_by_id(session: Session, id: UUID) -> int | None:
    t = session.get(Transcript, id)
    if not t:
        return None
    v = session.get(Video, t.video_id) if t.video_id else None
    return v.status if v else None


def save_transcript(
    session: Session,
    video_id: UUID,
    transcribed_by: UUID | None,
    data: dict,
) -> Transcript:
    t = get_latest_transcript_for_video(session, video_id)
    if t is None:
        t = Transcript(video_id=video_id)
    t.transcribed_by = transcribed_by
    t.transcript_data = json.dumps(data) if data is not None else "{}"
    t.transcript_date = datetime.now(timezone.utc)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def update_transcript(
    session: Session,
    video_id: UUID,
    data: dict,
) -> Transcript | None:
    """Update the existing transcript row for a video in place (no new row)."""
    t = get_latest_transcript_for_video(session, video_id)
    if t is None:
        return None
    t.transcript_data = json.dumps(data) if data is not None else "{}"
    t.transcript_date = datetime.now(timezone.utc)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def update_transcript_by_id(
    session: Session,
    transcript_id: UUID,
    data: dict,
) -> Transcript | None:
    """Update a specific transcript row by id in place (no new row)."""
    t = get_transcript_by_id(session, transcript_id)
    if t is None:
        return None
    t.transcript_data = json.dumps(data) if data is not None else "{}"
    t.transcript_date = datetime.now(timezone.utc)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def update_transcript_status(
    session: Session,
    transcript_id: UUID,
    status: int,
) -> Transcript | None:
    """Update a specific transcript row's status."""
    t = get_transcript_by_id(session, transcript_id)
    if t is None:
        return None
    t.status = status
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def update_status(session: Session, id: UUID, status: int) -> Video:
    """Update the queued status on a video resource by its id."""
    v = session.get(Video, id)
    if not v:
        raise ValueError(f"Video {id} not found")
    v.status = status
    session.add(v)
    session.commit()
    session.refresh(v)
    return v


def get_orphaned_transcriptions(session: Session):
    """Videos left Transcripting (e.g. after a crash) — candidates to re-queue."""
    stmt = select(Video).where(Video.status == TranscriptStatus.Transcripting.value)
    return session.exec(stmt).all()


# ── Queue — DB-backed via Video.status ───────────────────────────────────────

def claim_next_queued(session: Session) -> Video | None:
    """
    Pull the oldest InQueue video and atomically mark it as Transcripting.
    Returns None if nothing is queued.
    """
    v = session.exec(
        select(Video)
        .where(Video.status == TranscriptStatus.InQueue.value)
        .order_by(Video.date_created)
        .limit(1)
    ).first()

    if not v:
        return None

    v.status = TranscriptStatus.Transcripting.value
    session.add(v)
    session.commit()
    session.refresh(v)
    return v


def check_exist_and_create_video_entry(
    session: Session, form: YoutubeTranscriptRequestForm, user_id: UUID
) -> tuple[Video, Transcript | None]:
    """
    Idempotent: if the resource already has a video entry, reuse it; otherwise
    create a new ``video`` resource. A fresh transcription attempt (transcript
    row) is created only when none exists for that video yet, then queued.
    """
    video = None
    if form.resource_id:
        video = get_video_by_resource(session, form.resource_id, form.original_source)

    if not video:
        video = Video(
            original_source=form.original_source,
            resource_id=form.resource_id,
            resource_url=form.resource_url,
            thumbnail_url=form.thumbnail_url,
            name=form.name,
            status=TranscriptStatus.InQueue.value,
            public=form.public,
        )
        session.add(video)
        session.flush()

    transcript = get_latest_transcript_for_video(session, video.id)
    if not transcript:
        transcript = Transcript(
            video_id=video.id,
            transcribed_by=user_id,
        )
        session.add(transcript)
        session.commit()
    else:
        session.commit()

    session.refresh(video)
    return video, transcript


def get_user_history(session: Session, user_id: UUID) -> UserHistoryListResponse:
    """
    Returns the catalog of video resources. With transcriptionhistory removed,
    history is now the shared list of videos (each carrying its latest
    transcript status / transcription attempt).
    """
    results = session.exec(
        select(Video).order_by(Video.date_created.desc())
    ).all()

    history_items = []
    for v in results:
        t = get_latest_transcript_for_video(session, v.id)
        history_items.append(UserHistoryResponse(
            history_id=v.id,
            video_id=v.id,
            transcript_id=t.id if t else None,
            name=v.name,
            thumbnail_url=v.thumbnail_url,
            original_source=v.original_source,
            date_created=v.date_created,
            status=v.status,
            is_transcribed=t is not None and v.status == TranscriptStatus.Finish.value,
        ))

    return UserHistoryListResponse(items=history_items, total=len(history_items))


def remove_history_entry(session: Session, history_id: UUID, user_id: UUID) -> bool:
    """
    Removes a video resource (and its cascading transcripts/progress) by id.
    History ids are video ids in the new schema.
    """
    video = session.get(Video, history_id)
    if not video:
        return False
    session.delete(video)
    session.commit()
    return True


# ── Video Progress Queries ─────────────────────────────────────────────────

def get_video_progress(
    session: Session, user_id: UUID, video_id: UUID
) -> VideoProgress | None:
    return session.exec(
        select(VideoProgress).where(
            VideoProgress.user_id == user_id,
            VideoProgress.video_id == video_id,
        )
    ).first()


def save_video_progress(
    session: Session,
    user_id: UUID,
    video_id: UUID,
    progress: float,
) -> VideoProgress:
    p = get_video_progress(session, user_id, video_id)
    if not p:
        p = VideoProgress(
            user_id=user_id,
            video_id=video_id,
            progress=progress,
        )
        session.add(p)
    else:
        p.progress = progress
        p.updated_at = datetime.now(timezone.utc)
        session.add(p)
    session.commit()
    session.refresh(p)
    return p


# ── Listing / visited ───────────────────────────────────────────────────────────

def list_transcripts_for_video(
    session: Session,
    video_id: UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[Transcript]:
    """Return the transcription attempts (transcript rows) for a specific video."""
    stmt = (
        select(Transcript)
        .where(Transcript.video_id == video_id)
        .order_by(Transcript.transcript_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return session.exec(stmt).all()


def get_visited_videos(
    session: Session, user_id: UUID
) -> list[tuple["VideoProgress", Video | None]]:
    """Return the user's visited videos, derived from saved playback progress."""
    stmt = (
        select(VideoProgress)
        .where(VideoProgress.user_id == user_id)
        .order_by(VideoProgress.updated_at.desc())
    )
    progress_rows = session.exec(stmt).all()
    return [
        (vp, session.get(Video, vp.video_id))
        for vp in progress_rows
    ]
