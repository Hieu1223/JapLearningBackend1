from sqlmodel import Session, select
from ...database import engine
from ...database import (
    get_orphaned_transcriptions,
)
from ...database.transcription.queries import (
    get_transcript_by_id,
    get_video_by_id,
    update_transcript_by_id,
    update_transcript_status,
)
from ..youtube.youtube_download_utils import download_from_url
from ..providers.whisperx_modal_transcriber import transcribe_url
from ...database import (
    TranscriptStatus,
    TranscriptInfoResponse,
    Video,
)
from ..pipeline.transcript_token_merger import merge_transcript_tokens
from uuid import UUID
import tempfile


def _transcribe_core(
    session: Session,
    transcript_id: UUID,
) -> UUID:
    """Transcribe for a specific transcript row. Only the Transcript is touched
    (status + transcript_data); the Video is never modified."""
    transcript = get_transcript_by_id(session, transcript_id)
    if transcript is None:
        raise ValueError(f"Transcript {transcript_id} not found")
    video = get_video_by_id(session, transcript.video_id) if transcript.video_id else None
    if video is None:
        raise ValueError(f"Video for transcript {transcript_id} not found")

    try:
        update_transcript_status(session, transcript_id, TranscriptStatus.Transcripting.value)

        data = transcribe_url(video.resource_url)
        print(data)
        raw_segments = data.get("segments", []) if isinstance(data, dict) else []
        merged = merge_transcript_tokens(raw_segments)
        tokenized = {
            "segments": [[tok.model_dump(mode="json") for tok in seg] for seg in merged],
        }

        update_transcript_by_id(session, transcript_id, tokenized)
        update_transcript_status(session, transcript_id, TranscriptStatus.Finish.value)

        return transcript_id

    except Exception:
        update_transcript_status(session, transcript_id, TranscriptStatus.Error.value)
        raise


def transcribe_upload(
    resource_id: str, user_id: UUID, transcript_id: UUID | None = None
) -> TranscriptInfoResponse:
    with Session(engine) as session:
        transcript_id = transcript_id or _latest_transcript_id_for_resource(
            session, resource_id
        )
        if transcript_id is None:
            raise ValueError(f"No transcript for resource_id {resource_id}")

        video = get_video_by_id(session, get_transcript_by_id(session, transcript_id).video_id)
        _transcribe_core(session, transcript_id)
        return TranscriptInfoResponse(
            id=video.id,
            video_id=video.id,
            original_source=video.original_source,
            thumbnail_url=video.thumbnail_url,
            resource_url=video.resource_url,
            resource_id=video.resource_id,
            name=video.name,
            status=video.status,
        )


def _latest_transcript_id_for_resource(session: Session, resource_id: str) -> UUID | None:
    video = session.exec(
        select(Video).where(Video.resource_id == resource_id)
    ).first()
    if video is None:
        return None
    from ...database.transcription.queries import get_latest_transcript_for_video
    t = get_latest_transcript_for_video(session, video.id)
    return t.id if t else None


def recover_orphaned_transcript(session: Session):
    orphaned = get_orphaned_transcriptions(session)

    results = []
    for v in orphaned:
        from ...database.transcription.queries import get_latest_transcript_for_video
        t = get_latest_transcript_for_video(session, v.id)
        if t is None:
            continue
        try:
            _transcribe_core(session, t.id)
            results.append(v)
        except Exception as e:
            print(f"[ERROR] Failed to recover video {v.id}: {e}")
            continue

    return results
