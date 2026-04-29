from sqlmodel import SQLModel, Field, UniqueConstraint
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime, timezone


class QueryVRFToken(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("query", name="uq_queryvrf_query"),)

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    query: str = Field(index=True)
    token: str = Field()


class Manga(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("manga_url", name="uq_manga_url"),)

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str = Field(default="")
    manga_url: str = Field()
    manga_cover_url: str = Field(default="")
    has_transcripted_chapters: bool = Field(default=False)


class Chapter(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("link", name="uq_chapter_link"),)

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    link: str = Field()
    num: str = Field(default="")
    title: str = Field(default="")
    transcripted: bool = Field(default=False)
    ocr_data: str = Field(default="")
    image_list: str = Field(default="[]")


class ReadHistory(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "manga_id", name="uq_readhistory_user_manga"),
    )

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    manga_id: UUID = Field(foreign_key="manga.id", index=True)
    chapter_id: UUID = Field(foreign_key="chapter.id", index=True)
    current_page: int = Field(default=0)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )