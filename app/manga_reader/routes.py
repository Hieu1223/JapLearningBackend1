from fastapi import APIRouter
from typing import Optional
from ..database import (
    SessionDep
)
from .manga_extractor import MangafireExtractor

router = APIRouter(tags = ['Manga'])


@router.get("/search")
async def search_manga(
    session: SessionDep,
    query : Optional[str],
):
    mangas = await MangafireExtractor(session).search(query)
    return mangas

@router.get('/chapter_list')
async def get_chapter_list(
    session : SessionDep,
    manga_url : str
):
    return await MangafireExtractor(session).get_chapter_list(manga_url)

@router.get('/read')
async def get_images(
    session : SessionDep,
    chapter_url : str
):
    return await MangafireExtractor(session).get_chapter_images(chapter_url)

@router.get('/ocr_data')
async def get_ocr_data(
    session: SessionDep,
    chapter_url : str
):
    pass