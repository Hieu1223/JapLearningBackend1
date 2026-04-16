import modal
import json
from ..database.manga_reader.queries import (
    get_cached_chapter_info, 
    update_chapter_ocr
)

# Initialize the remote Modal class
ocr = modal.Cls.from_name("manga-ocr-threaded-app", "OCR")()

async def do_ocr(session, chapter_url: str):
    # 1. Fetch from DB. If it's not there, something is wrong with the flow.
    chapter = get_cached_chapter_info(session, chapter_url)
    
    if not chapter:
        raise Exception(f"Chapter record not found for URL: {chapter_url}. Ensure manga is scraped first.")

    # 2. Return cached OCR if it exists
    if chapter.transcripted:
        return chapter.ocr_data
    
    # 3. Use the image list already stored in the DB
    # We assume image_list is never empty if the chapter was created correctly
    if not chapter.image_list or chapter.image_list == "{}":
        raise Exception(f"Chapter found but image_list is empty for ID: {chapter.id}")

    image_urls = json.loads(chapter.image_list)

    # 4. Run remote OCR via Modal
    # We only reach this if transcripted is False and image_list exists
    res = ocr.do_ocr.remote(image_urls)

    # 5. Save results back to DB
    ocr_result_string = json.dumps(res) if not isinstance(res, str) else res
    update_chapter_ocr(session, chapter.id, ocr_result_string)

    return res