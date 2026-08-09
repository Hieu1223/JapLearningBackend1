from typing import Optional
from uuid import UUID
from sqlmodel import Session

from ..database.web_novel.queries import (
    search_web_novels,
    get_web_novel_by_id,
    get_chapter_by_id,
    get_chapters_for_novel,
    create_web_novel,
    create_chapter,
    update_chapter_content,
)
from .schema import (
    WebNovelResponse,
    WebNovelChapterResponse,
)


def _web_novel_response(novel, chapters) -> WebNovelResponse:
    return WebNovelResponse(
        id=novel.id,
        author=novel.author,
        date_published=novel.date_published,
        summary=novel.summary,
        chapters=chapters,
    )


def _chapter_response(chapter) -> WebNovelChapterResponse:
    return WebNovelChapterResponse(
        id=chapter.id,
        name=chapter.name,
        updated_at=chapter.updated_at,
        content=chapter.content,
    )


class WebNovelService:

    def search_novels(
        self,
        session: Session,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[WebNovelResponse]:
        novels = search_web_novels(session, query, limit, offset)
        result = []
        for novel in novels:
            chapters = get_chapters_for_novel(session, novel.id)
            result.append(_web_novel_response(novel, [_chapter_response(c) for c in chapters]))
        return result

    def get_novel_by_id(self, session: Session, novel_id: UUID) -> Optional[WebNovelResponse]:
        novel = get_web_novel_by_id(session, novel_id)
        if not novel:
            return None
        chapters = get_chapters_for_novel(session, novel_id)
        return _web_novel_response(novel, [_chapter_response(c) for c in chapters])

    def get_chapter_by_id(self, session: Session, chapter_id: UUID) -> Optional[WebNovelChapterResponse]:
        chapter = get_chapter_by_id(session, chapter_id)
        if not chapter:
            return None
        return _chapter_response(chapter)

    def update_chapter_content(
        self,
        session: Session,
        chapter_id: UUID,
        content: str,
    ) -> Optional[WebNovelChapterResponse]:
        chapter = update_chapter_content(session, chapter_id, content)
        if not chapter:
            return None
        return _chapter_response(chapter)

    def create_novel(
        self,
        session: Session,
        author: str,
        date_published: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> WebNovelResponse:
        from datetime import datetime
        novel = create_web_novel(
            session=session,
            author=author,
            date_published=datetime.fromisoformat(date_published) if date_published else None,
            summary=summary,
        )
        return _web_novel_response(novel, [])

    def read_chapter(
        self,
        session: Session,
        chapter_id: UUID,
    ) -> Optional[WebNovelChapterResponse]:
        return self.get_chapter_by_id(session, chapter_id)