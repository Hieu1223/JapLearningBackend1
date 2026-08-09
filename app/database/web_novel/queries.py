import json
from datetime import datetime, timezone
from sqlmodel import Session, select
from uuid import UUID
from typing import Optional, List

from .schema import WebNovel, WebNovelChapter


def search_web_novels(session: Session, query: str, limit: int = 20, offset: int = 0) -> list[WebNovel]:
    stmt = (
        select(WebNovel)
        .where(WebNovel.author.ilike(f"%{query}%") | WebNovel.id.cast(str).ilike(f"%{query}%"))
        .limit(limit)
        .offset(offset)
    )
    return list(session.exec(stmt).all())


def get_web_novel_by_id(session: Session, novel_id: UUID) -> Optional[WebNovel]:
    return session.get(WebNovel, novel_id)


def get_chapter_by_id(session: Session, chapter_id: UUID) -> Optional[WebNovelChapter]:
    return session.get(WebNovelChapter, chapter_id)


def get_chapters_for_novel(session: Session, novel_id: UUID) -> list[WebNovelChapter]:
    stmt = (
        select(WebNovelChapter)
        .where(WebNovelChapter.web_novel_id == novel_id)
        .order_by(WebNovelChapter.updated_at.desc())
    )
    return list(session.exec(stmt).all())


def create_web_novel(
    session: Session,
    author: str,
    date_published: Optional[datetime] = None,
    summary: Optional[str] = None,
) -> WebNovel:
    novel = WebNovel(
        author=author,
        date_published=date_published,
        summary=summary,
    )
    session.add(novel)
    session.commit()
    session.refresh(novel)
    return novel


def create_chapter(
    session: Session,
    web_novel_id: UUID,
    name: str,
    content: Optional[str] = None,
) -> WebNovelChapter:
    chapter = WebNovelChapter(
        web_novel_id=web_novel_id,
        name=name,
        content=content,
    )
    session.add(chapter)
    session.commit()
    session.refresh(chapter)
    return chapter


def update_chapter_content(
    session: Session,
    chapter_id: UUID,
    content: str,
) -> Optional[WebNovelChapter]:
    chapter = session.get(WebNovelChapter, chapter_id)
    if not chapter:
        return None
    chapter.content = content
    chapter.updated_at = datetime.now(timezone.utc)
    session.add(chapter)
    session.commit()
    session.refresh(chapter)
    return chapter