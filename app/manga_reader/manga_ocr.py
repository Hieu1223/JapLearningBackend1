import modal
import json
from ..database.manga_reader.queries import (
    get_cached_chapter_info, 
    update_chapter_ocr
)
from .schema import OCRPage
import numpy as np

def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

# Initialize the remote Modal class
ocr = modal.Cls.from_name("manga-ocr-threaded-app", "OCR")()

async def do_ocr(session, chapter_url: str):
    # 1. Fetch from DB
    chapter = get_cached_chapter_info(session, chapter_url)
    if not chapter:
        raise Exception(f"Chapter record not found: {chapter_url}")

    # 2. Return cache
    if chapter.transcripted:
        return json.loads(chapter.ocr_data) # Return as list/dict, not string
    
    # 3. Get images
    if not chapter.image_list or chapter.image_list == "{}":
        raise Exception(f"image_list is empty for ID: {chapter.id}")

    image_urls = json.loads(chapter.image_list)

    # 4. Remote OCR
    res = await ocr.do_ocr.remote.aio(image_urls)
    
    # 5. Validate AND Dump
    # model_validate fixes the types (np.int32 -> int)
    # .model_dump() turns the object into a plain Python dict
    validated_data = [OCRPage.model_validate(page).model_dump() for page in res]

    # 6. Save to DB
    # Now validated_data is a plain list of dicts, so json.dumps works perfectly
    ocr_result_string = json.dumps(validated_data)
    update_chapter_ocr(session, chapter.id, ocr_result_string)

    return validated_data