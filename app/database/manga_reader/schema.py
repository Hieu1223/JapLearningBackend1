from sqlmodel import SQLModel, Field, UniqueConstraint, Relationship, Column
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy import Integer
from uuid import UUID, uuid4
from typing import Optional, List
from datetime import datetime, timezone


class MangaCreator(SQLModel, table=True):
    __tablename__ = "manga_creator"

    manga_id: UUID = Field(foreign_key="manga.id", ondelete="CASCADE", primary_key=True)
    creator_id: UUID = Field(foreign_key="creator.id", ondelete="CASCADE", primary_key=True)


class Manga(SQLModel, table=True):
    __tablename__ = "manga"
    __table_args__ = (
        UniqueConstraint("source_site", "source_id", name="uq_manga_source"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: Optional[int] = None
    source_site: str = Field(default="rawkuma")
    url: str = Field(index=True, unique=True)
    slug: str = Field(index=True, unique=True)
    title: str
    alternative_title: Optional[str] = None
    description: Optional[str] = None
    description_native: Optional[str] = None
    cover: Optional[str] = None
    status: Optional[str] = None
    manga_type: Optional[str] = None
    genre_ids: List[int] = Field(
        default_factory=list,
        sa_column=Column(PG_ARRAY(Integer), nullable=False, server_default="{}"),
    )
    released: Optional[str] = None
    serialization: Optional[str] = None
    score: Optional[float] = None
    views_daily: Optional[int] = None
    views_weekly: Optional[int] = None
    views_monthly: Optional[int] = None
    reader_count: Optional[int] = None
    published_at: Optional[datetime] = None
    source_modified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chapters: List["Chapter"] = Relationship(back_populates="manga")
    creators: List["Creator"] = Relationship(
        back_populates="mangas",
        link_model=MangaCreator,
    )


class Genre(SQLModel, table=True):
    __tablename__ = "genre"

    id: int = Field(primary_key=True)
    slug: str = Field(index=True)
    name: str = Field(index=True)


class Creator(SQLModel, table=True):
    __tablename__ = "creator"
    __table_args__ = (
        UniqueConstraint("source_term_id", name="uq_creator_source_term_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_term_id: int = Field(index=True)
    slug: str = Field(index=True)
    name: str = Field(index=True)
    role: str = Field()

    mangas: List["Manga"] = Relationship(
        back_populates="creators",
        link_model=MangaCreator,
    )


class Chapter(SQLModel, table=True):
    __tablename__ = "chapter"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    manga_id: UUID = Field(foreign_key="manga.id", index=True)
    title: str
    url: str = Field(index=True, unique=True)
    chapter_index: Optional[int] = None
    date: Optional[str] = None
    pages: str = Field(default="[]")  # JSON reconstruction template (base_url + pattern + page_count)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    manga: Optional[Manga] = Relationship(back_populates="chapters")
    ocr_result: List["OCRResult"] = Relationship(back_populates="chapter")


class OCRResult(SQLModel, table=True):
    __tablename__ = "ocr_result"
    __table_args__ = (
        UniqueConstraint("chapter_id", "page_number", name="uq_ocr_result_chapter_page"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chapter_id: UUID = Field(foreign_key="chapter.id", index=True, ondelete="CASCADE")
    page_number: int = Field(default=0)
    # Nullable, not cascaded on user delete
    ocr_by: Optional[UUID] = Field(default=None, foreign_key="user.id", nullable=True)
    ocr_data: str = Field(default="")  # raw JSON string
    ocr_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chapter: Optional[Chapter] = Relationship(back_populates="ocr_result")


class ReadHistory(SQLModel, table=True):
    __tablename__ = "readhistory"
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
