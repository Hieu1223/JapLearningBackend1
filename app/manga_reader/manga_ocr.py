import modal
ocr = modal.Cls.from_name("manga-ocr-threaded-app", "OCR")()
from .manga_extractor import MangafireExtractor
async def do_ocr(session,chapter_url: str):
    image_urls= await MangafireExtractor(session).get_chapter_images(chapter_url)
    res = ocr.do_ocr.remote(image_urls)
    return res