import os
import modal

QwenPipeline = modal.Cls.from_name("qwen_transcribe", "QwenPipeline")
pipeline = QwenPipeline()

PROXY = os.environ.get("HTTP_PROXY")


def transcribe_url(url: str) -> list:
    try:
        result = pipeline.transcribe_url.remote(url, PROXY)
    except Exception as e:
        return e
    return result