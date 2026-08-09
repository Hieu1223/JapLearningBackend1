from sqlmodel import Session, select
from ..database import engine
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
from ..tokenization.tokenize import merge_transcript_tokens
from ..transcription.schema import TranscriptResult, TokenTimestamp
from uuid import UUID
import tempfile


def _transcribe_core(
    session: Session,
    info: TranscriptInfoResponse
) -> TranscriptInfoResponse:
    try:
        update_status(session, info.id, TranscriptStatus.Transcripting.value)

        data = transcribe_url(info.resource_url)

        # When the transcript is received, tokenize each segment's text with
        # Sudachi and merge the morphemes using the WhisperX word timestamps,
        # replacing each segment's raw words with the merged tokens.
        try:
            result = TranscriptResult(**data)
            merged = merge_transcript_tokens(result.segments)
            for seg, seg_words in zip(result.segments, merged):
                seg.words = [
                    TokenTimestamp(token=w["token"], start=w["start"], end=w["end"])
                    for w in seg_words
                ]
            data = result.model_dump()
        except Exception as e:
            print(f"[WARN] token merge failed for transcript {info.id}: {e}")

        save_transcript(session, info.id, data)
        update_status(session, info.id, TranscriptStatus.Finish.value)

        return info

    except Exception:
        update_status(session, info.id, TranscriptStatus.Error.value)
        raise



def transcribe_upload(
    form: YoutubeTranscriptRequestForm,
    user_id: UUID
) -> TranscriptInfoResponse:
    with Session(engine) as session:
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