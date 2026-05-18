import modal
import subprocess
import os
from pathlib import Path
from fastapi import File
# Look up deployed class
Transcriber = modal.Cls.from_name("qwen_transcribe", "QwenPipeline")
download_media = modal.Function.from_name("qwen_transcribe", "download_media")
transcriber = Transcriber()


def transcribe(audio_bytes: bytes) -> list:
    try:
        result = transcriber.transcribe.remote(audio_bytes)
    except Exception as e:
        return e
    return result

def transcribe_url(url: str) -> dict | Exception:
    try:
        # Step 1: Download and convert on a cheap CPU container
        download_payload = download_media.remote(url)
        
        # Step 2: Initialize the GPU class reference and pass the payload
        # (Reuses the already warmed-up model if the container is hot)
        result = transcriber.transcribe_paths.remote(download_payload)
        
        return result
    except Exception as e:
        return e