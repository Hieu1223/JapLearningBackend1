from typing import Optional, List
from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel


class WebNovelResponse(SQLModel):
    id: UUID
    author: str
    date_published: Optional[datetime] = None
    summary: Optional[str] = None
    chapters: List["WebNovelChapterResponse"] = []


class WebNovelChapterResponse(SQLModel):
    id: UUID
    name: str
    updated_at: datetime
    content: Optional[str] = None


class CreateWebNovelRequest(SQLModel):
    author: str
    date_published: Optional[datetime] = None
    summary: Optional[str] = None


class CreateChapterRequest(SQLModel):
    name: str
    content: Optional[str] = None


class WebNovelReadHistoryResponse(SQLModel):
    id: UUID
    user_id: UUID
    web_novel_id: UUID
    chapter_id: UUID
    updated_at: datetime


class WebNovelReadHistoryUpdate(SQLModel):
    web_novel_id: UUID
    chapter_id: UUID
