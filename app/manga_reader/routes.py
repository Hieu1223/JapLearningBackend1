from fastapi import APIRouter, HTTPException
from typing import Optional
from ..database import SessionDep

# Cleaned up imports for clarity
from .rawkuma_extractor import NatsuExtractor
from .manga_extractor import MangafireExtractor
from .manga_ocr import do_ocr
from .schema import MangaInfo, ChapterInfo, OCRResponse

router = APIRouter(tags=['Manga'])

@router.get("/search")
async def search_manga(
    session: SessionDep,
    query: Optional[str],
) -> list[MangaInfo]:
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        # 1. Try NatsuID (Rawkuma) first
        natsu = NatsuExtractor(session)
        results = await natsu.search(query)
        
        # 2. If no results found, fallback to Mangafire
        if not results:
            return await MangafireExtractor(session).search(query)
            
        return results
    except Exception as e:
        # If Natsu fails entirely, try Mangafire as a last resort before erroring
        try:
            return await MangafireExtractor(session).search(query)
        except:
            raise HTTPException(status_code=500, detail=str(e))


@router.get('/chapter_list')
async def get_chapter_list(
    session: SessionDep,
    manga_url: str
) -> list[ChapterInfo]:
    if not manga_url:
        raise HTTPException(status_code=400, detail="manga_url is required")

    try:
        # Determine extractor based on URL
        # NatsuID uses the full Base URL (e.g., rawkuma.net)
        natsu = NatsuExtractor(session)
        if natsu.base_url in manga_url:
            return await natsu.get_chapter_list(manga_url)
        else:
            return await MangafireExtractor(session).get_chapter_list(manga_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/read')
async def get_images(
    session: SessionDep,
    chapter_url: str
) -> list[str]:
    if not chapter_url:
        raise HTTPException(status_code=400, detail="chapter_url is required")

    try:
        # Determine extractor based on URL
        natsu = NatsuExtractor(session)
        if natsu.base_url in chapter_url:
            return await natsu.get_page_images(chapter_url)
        else:
            # Note: Your MangafireExtractor uses 'get_chapter_images' 
            return await MangafireExtractor(session).get_chapter_images(chapter_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/ocr_data')
async def get_ocr_data(
    session: SessionDep,
    chapter_url: str
) -> OCRResponse:
    if not chapter_url:
        raise HTTPException(status_code=400, detail="chapter_url is required")

    try:
        data = await do_ocr(session, chapter_url)
        return OCRResponse(pages=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))