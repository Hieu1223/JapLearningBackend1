import os
import modal

WhisperXTranscriber = modal.Cls.from_name("whisperx_transcribe", "WhisperXTranscriber")
pipeline = WhisperXTranscriber()
PROXY = os.environ.get("HTTP_PROXY")


def transcribe_url(url: str) -> list:
    try:
        result = pipeline.transcribe_url.remote(url, PROXY)
    except Exception as e:
        return e
    return result