from sqlmodel import Session
from .db import (
    check_exist_and_create_transcription_entry,
    update_status,
    save_transcript,
)
from .utils import download_from_url
from .modal_transcribe import transcribe
from .schema import (
    TranscriptStatus,
    YoutubeTranscriptRequestForm,
    TranscriptInfoResponse,
)


def _run(session: Session, form: YoutubeTranscriptRequestForm) -> TranscriptInfoResponse:
    info = check_exist_and_create_transcription_entry(session, form)

    update_status(session, info.id, TranscriptStatus.Transcripting.value)  # Step 6

    file_path = download_from_url("temp/",form.resource_url)
    with open(file_path,'rb') as f:
        audio_bytes = f.read()
    data = transcribe(audio_bytes)
    save_transcript(session, info.id, data)                                 # Steps 8-9
    update_status(session, info.id, TranscriptStatus.Finish.value)          # Step 10
    return info



def transcribe_upload(session: Session, form: YoutubeTranscriptRequestForm) -> TranscriptInfoResponse:
    return _run(session, form)