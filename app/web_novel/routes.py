import os
from fastapi import APIRouter, HTTPException
from uuid import UUID

from ..container import Container, get_db_session
from .schema import (
    WebNovelResponse,
    WebNovelChapterResponse,
)

router = APIRouter(tags=["Web Novel"])

_container = Container()


@router.get("/novels/search", response_model=list[WebNovelResponse], tags=["Web Novel"], description="Search the web-novel catalog by free-text query, returning a paginated list of matching novels")
def search_novels(
    q: str,
    limit: int = 20,
    offset: int = 0,
):
    session = get_db_session()
    return _container.web_novel_service.search_novels(session, q, limit, offset)


@router.get("/novels/{novel_id}", response_model=WebNovelResponse, tags=["Web Novel"], description="Fetch the full details of a single web novel by its id")
def get_novel(
    novel_id: UUID,
):
    session = get_db_session()
    result = _container.web_novel_service.get_novel_by_id(session, novel_id)
    if not result:
        raise HTTPException(status_code=404, detail="Novel not found")
    return result


@router.get("/chapters/{chapter_id}", response_model=WebNovelChapterResponse, tags=["Web Novel"], description="Fetch the content and metadata of a single chapter by its id")
def read_chapter(
    chapter_id: UUID,
):
    session = get_db_session()
    result = _container.web_novel_service.read_chapter(session, chapter_id)
    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return result