from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint


class WebNovel(SQLModel, table=True):
    __tablename__ = "web_novel"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    author: str = Field(index=True)
    date_published: Optional[datetime] = None
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chapters: List["WebNovelChapter"] = Relationship(back_populates="web_novel")


class WebNovelChapter(SQLModel, table=True):
    __tablename__ = "web_novel_chapter"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    web_novel_id: UUID = Field(foreign_key="web_novel.id", index=True)
    name: str = Field(index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: Optional[str] = None

    web_novel: Optional[WebNovel] = Relationship(back_populates="chapters")


class WebNovelReadHistory(SQLModel, table=True):
    __tablename__ = "web_novel_readhistory"
    __table_args__ = (
        UniqueConstraint("user_id", "web_novel_id", name="uq_web_novel_readhistory_user_novel"),
    )

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    web_novel_id: UUID = Field(foreign_key="web_novel.id", index=True)
    chapter_id: UUID = Field(foreign_key="web_novel_chapter.id", index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
