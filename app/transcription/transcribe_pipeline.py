from sqlmodel import Session,select
from ..database import (
    check_exist_and_create_transcription_entry,
    update_status,
    save_transcript,
    get_orphaned_transcriptions
)
from .utils import download_from_url
from .modal_transcribe import transcribe_url
from ..database import (
    TranscriptStatus,
    TranscriptInfoResponse,
    YoutubeTranscriptRequestForm
)
from uuid import UUID
import tempfile


def _transcribe_core(
    session: Session,
    info: TranscriptInfoResponse
) -> TranscriptInfoResponse:
    try:
        update_status(session, info.id, TranscriptStatus.Transcripting.value)

        data = transcribe_url(info.resource_url)

        save_transcript(session, info.id, data)
        update_status(session, info.id, TranscriptStatus.Finish.value)

        return info

    except Exception:
        update_status(session, info.id, TranscriptStatus.Error.value)
        raise


def transcribe_upload(
    session: Session,
    form: YoutubeTranscriptRequestForm,
    user_id: UUID
) -> TranscriptInfoResponse:

    info = check_exist_and_create_transcription_entry(session, form, user_id)

    return _transcribe_core(session, info)




def recover_orphaned_transcript(session: Session):
    orphaned = get_orphaned_transcriptions(session)

    results = []
    for t in orphaned:
        info = TranscriptInfoResponse(
            id=t.id,
            original_source=t.original_source,
            thumnail_url=t.thumnail_url,
            resource_url=t.resource_url,
            resource_id=t.resource_id,
            status=t.status,
        )

        try:
            result = _transcribe_core(session, info)
            results.append(result)

        except Exception as e:
            print(f"[ERROR] Failed to recover transcript {t.id}: {e}")

            continue

    return results