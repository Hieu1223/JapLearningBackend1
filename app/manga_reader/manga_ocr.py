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
        if not chapter.image_list or chapter.image_list == "[]":
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
        print(res)
        #print(ocr_result_string)
        update_chapter_ocr(session, chapter.id, ocr_result_string)
    except Exception as e:
        print(e)
    return validated_data



async def do_ocr_stream(session, chapter_url: str):
    print(chapter_url)
    try:
        chapter = get_cached_chapter_info(session, chapter_url)
        if not chapter:
            raise Exception(f"Chapter record not found: {chapter_url}")

        if chapter.transcripted:
            for page in json.loads(chapter.ocr_data):
                yield page
            return

        if not chapter.image_list or chapter.image_list == "[]":
            raise Exception(f"image_list is empty for ID: {chapter.id}")

        image_urls = json.loads(chapter.image_list)

        all_pages = []
        async for batch in ocr.stream_ocr_batches.remote_gen.aio(image_urls):
            for page in batch:
                validated = OCRPage.model_validate(page).model_dump()
                all_pages.append(validated)
                yield validated  # stream each page as it comes

        # Save to DB once all pages are collected
        update_chapter_ocr(session, chapter.id, json.dumps(all_pages))

    except Exception as e:
        print(e)