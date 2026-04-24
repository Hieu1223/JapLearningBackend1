import modal
import subprocess
import os
from pathlib import Path
from fastapi import File
# Look up deployed class
Transcriber = modal.Cls.from_name("whisperx_transcribe", "Transcriber")
transcriber = Transcriber()



def transcribe(audio_bytes: bytes) -> list:
    try:
        result = transcriber.transcribe.remote.aio(audio_bytes)
    except Exception as e:
        return e
    return result