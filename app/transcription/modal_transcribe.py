import modal
import subprocess
import os
from pathlib import Path
from fastapi import File
# Look up deployed class
Transcriber = modal.Cls.from_name("qwen_transcribe", "QwenTranscriber")
transcriber = Transcriber()



def transcribe(audio_bytes: bytes) -> list:
    try:
        result = transcriber.transcribe.remote(audio_bytes)
    except Exception as e:
        return e
    return result

def transcribe_url(url:str) -> list:
    try:
        result = transcriber.transcribe_url.remote(url)
    except Exception as e:
        return e
    return result