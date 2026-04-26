from fastapi import APIRouter, HTTPException
from typing import Optional
from ..database import SessionDep

# Cleaned up imports for clarity
from .rawkuma_extractor import NatsuExtractor
from .manga_extractor import MangafireExtractor
from .manga_ocr import do_ocr
from .schema import MangaInfo, ChapterInfo, OCRResponse
from .sort_type import SortType
from fastapi import Query


router = APIRouter(tags=['Manga'])
@router.get("/search")
async def search_manga(
    session: SessionDep,
    query: Optional[str],
    page: int = Query(1, ge=1),
    sort: SortType = Query("recently_updated")
) -> list[MangaInfo]:
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    # Normalize query for consistent caching/searching
    query_clean = query.strip()

    try:
        # 1. Primary Source: NatsuID (Rawkuma)
        # Internal logic now forces 'type[]=manga' for Japanese content
        natsu = NatsuExtractor(session)
        results = natsu.search(query=query_clean, page=page, sort=sort)
        
        # 2. Fallback: Mangafire
        # Triggered if Natsu returns no results or if page 1 is empty
        if not results:
            mf = MangafireExtractor(session)
            return await mf.search(query=query_clean, page=page, sort=sort)
            
        return results

    except Exception as e:
        # If Natsu logic crashes (e.g., Nonce retrieval fails), 
        # attempt Mangafire as the final fallback.
        try:
            mf = MangafireExtractor(session)
            return await mf.search(query=query_clean, page=page, sort=sort)
        except Exception as inner_e:
            raise HTTPException(
                status_code=500, 
                detail=f"Both sources failed. Original error: {str(e)} | Fallback error: {str(inner_e)}"
            )

@router.get('/chapter_list')
async def get_chapter_list(
    session: SessionDep,
    manga_url: str,
) -> list[ChapterInfo]:
    if not manga_url:
        raise HTTPException(status_code=400, detail="manga_url is required")

    try:
        # Determine extractor based on URL
        # NatsuID uses the full Base URL (e.g., rawkuma.net)
        natsu = NatsuExtractor(session)
        if natsu.base_url in manga_url:
            return natsu.get_chapter_list(manga_url)
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
            return natsu.get_page_images(chapter_url)
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