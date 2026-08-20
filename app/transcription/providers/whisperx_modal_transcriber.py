import os
import modal

WhisperXTranscriber = modal.Cls.from_name("whisperx_transcribe", "WhisperXTranscriber")
pipeline = WhisperXTranscriber()
PROXY = os.environ.get("HTTP_PROXY")


def transcribe_url(url: str) -> dict:
    result = pipeline.transcribe_url.remote(url, PROXY)
    print(result)
    if isinstance(result, Exception):
        raise result
    return result
