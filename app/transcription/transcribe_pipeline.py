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
    TranscriptionHistory,
    TranscriptInfoResponse,
    YoutubeTranscriptRequestForm
)
from uuid import UUID
import tempfile

def create_transcription_history(session: Session, user_id: UUID, transcript_id: UUID):
    statement = select(TranscriptionHistory).where(TranscriptionHistory.user_id == user_id and TranscriptionHistory.transcript_id == transcript_id)
    existing = session.exec(statement)
    if existing:
        return
    history_entry = TranscriptionHistory(
        user_id= user_id,
        transcript_id=transcript_id,
    )
    session.add(history_entry)
    session.commit()



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
        update_status(session, info.id, TranscriptStatus.Transcripting.value)
        raise


def transcribe_upload(
    session: Session,
    form: YoutubeTranscriptRequestForm
) -> TranscriptInfoResponse:

    info = check_exist_and_create_transcription_entry(session, form)

    create_transcription_history(session, form.user_id, info.id)

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
            # 👇 mark as error
            update_status(session, t.id, TranscriptStatus.Error.value)

            # 👇 log it (replace with proper logger later)
            print(f"[ERROR] Failed to recover transcript {t.id}: {e}")

            continue

    return results