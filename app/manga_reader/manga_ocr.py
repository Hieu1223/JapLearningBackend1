import modal
import json
from ..database.manga_reader.queries import (
    get_cached_chapter_info, 
    update_chapter_ocr
)
from .schema import OCRPage

# Initialize the remote Modal class
ocr = modal.Cls.from_name("manga-ocr-threaded-app", "OCR")()

async def do_ocr(session, chapter_url: str):
    print(chapter_url)
    try:
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
        print(res)
        validated_data = [OCRPage.model_validate(page).model_dump() for page in res]
        # 6. Save to DB
        # Now validated_data is a plain list of dicts, so json.dumps works perfectly
        ocr_result_string = json.dumps(validated_data)
        #print(ocr_result_string)
        update_chapter_ocr(session, chapter.id, ocr_result_string)
    except Exception as e:
        print(e)
    return validated_data