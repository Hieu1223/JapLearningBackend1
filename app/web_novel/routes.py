import os
from fastapi import APIRouter, HTTPException
from uuid import UUID

from ..security.auth import CurrentUser
from ..container import Container, get_db_session
from ..database import SessionDep
from .schema import (
    CreateWebNovelRequest,
    CreateChapterRequest,
    WebNovelResponse,
    WebNovelChapterResponse,
)

router = APIRouter(tags=["Web Novel"])

_container = Container()

NOVEL_REQUEST_SERVER_URL = os.getenv("NOVEL_REQUEST_SERVER_URL", "http://localhost:8001")


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


@router.post("/novels", response_model=WebNovelResponse, tags=["Web Novel"], description="Create a new web novel record with the given author, publication date and summary")
def create_novel(
    req: CreateWebNovelRequest,
    user: CurrentUser,
):
    session = get_db_session()
    return _container.web_novel_service.create_novel(
        session,
        author=req.author,
        date_published=req.date_published.isoformat() if req.date_published else None,
        summary=req.summary,
    )


@router.post("/novels/{novel_id}/chapters", response_model=WebNovelChapterResponse, tags=["Web Novel"], description="Append a new chapter to an existing novel and return the created chapter")
def create_chapter(
    novel_id: UUID,
    req: CreateChapterRequest,
    user: CurrentUser,
    session: SessionDep,
):
    from ..database.web_novel.queries import create_chapter, get_web_novel_by_id
    
    novel = get_web_novel_by_id(session, novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    
    chapter = create_chapter(
        session,
        web_novel_id=novel_id,
        name=req.name,
        content=req.content,
    )
    result = _container.web_novel_service.get_chapter_by_id(session, chapter.id)
    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return result


@router.patch("/chapters/{chapter_id}", response_model=WebNovelChapterResponse, tags=["Web Novel"], description="Replace the content of an existing chapter and return the updated chapter")
def update_chapter(
    chapter_id: UUID,
    req: CreateChapterRequest,
    user: CurrentUser,
):
    session = get_db_session()
    result = _container.web_novel_service.update_chapter_content(session, chapter_id, req.content)
    if not result:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return result


@router.post("/novels/request", tags=["Web Novel"], description="Submit a web-novel URL to an external ingestion server to request that it be fetched and indexed; the request is dispatched asynchronously")
def request_novel(
    novel_url: str,
    user: CurrentUser,
):
    import httpx
    
    async def send_to_external_server():
        async with httpx.AsyncClient() as client:
            payload = {
                "user_id": str(user.id),
                "novel_url": novel_url,
            }
            await client.post(f"{NOVEL_REQUEST_SERVER_URL}/novels/request", json=payload, timeout=30.0)
    
    import asyncio
    asyncio.create_task(send_to_external_server())
    
    return {"success": True, "novel_url": novel_url}