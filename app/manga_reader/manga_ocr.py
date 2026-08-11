import modal
from typing import AsyncIterator

from ..tokenization.tokenize import build_dependency_tree
from .schema import OCRPage, OCRBlock

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


def _analyze_lines(lines: list[str]) -> list[list[dict]]:
    """Run GiNZA tokenization + dependency analysis on each OCR line.

    Returns a list (one per line) of dependency trees (as dicts) so it can be
    stored alongside the OCR data as JSON.
    """
    return [
        [tree.model_dump() for tree in build_dependency_tree(line)]
        for line in lines
        if line.strip()
    ]


def analyze_ocr_page(page: OCRPage) -> OCRPage:
    """Augment each OCR block with GiNZA tokenization + dependency analysis.

    Analysis is computed per block line (the natural manga text layout) and
    attached to the block. No page-level analysis is stored to avoid duplicate
    data.
    """
    for block in page.blocks:
        if block.lines:
            block.analyze = _analyze_lines(block.lines)

    return page