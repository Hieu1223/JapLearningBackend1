import modal
from typing import AsyncIterator

from .schema import OCRPage

# Initialize the remote Modal class
ocr = modal.Cls.from_name("manga-ocr-threaded-app", "OCR")()


async def do_ocr_stream(image_urls: list[str]) -> AsyncIterator[dict]:
    """
    Pure OCR generator. Accepts image URLs directly, streams validated page dicts.
    No DB reads or writes — the controller owns that.
    """
    if not image_urls:
        raise ValueError("image_urls is empty")

    async for batch in ocr.stream_ocr_batches.remote_gen.aio(image_urls):
        for page in batch:
            validated = OCRPage.model_validate(page).model_dump()
            yield validated