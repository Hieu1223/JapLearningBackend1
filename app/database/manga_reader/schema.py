from sqlmodel import SQLModel, Field, UniqueConstraint, Relationship
from uuid import UUID, uuid4
from typing import Optional, List
from datetime import datetime, timezone


class Manga(SQLModel, table=True):
    __tablename__ = "manga"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    url: str = Field(index=True, unique=True)
    slug: str = Field(index=True, unique=True)
    title: str
    description: Optional[str] = None
    cover: Optional[str] = None
    status: Optional[str] = None
    genres: Optional[str] = None  # JSON string
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chapters: List["Chapter"] = Relationship(back_populates="manga")


class Chapter(SQLModel, table=True):
    __tablename__ = "chapter"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    manga_id: UUID = Field(foreign_key="manga.id", index=True)
    title: str
    url: str = Field(index=True, unique=True)
    chapter_index: Optional[int] = None
    date: Optional[str] = None
    pages: str = Field(default="[]")  # JSON string of image URLs
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    manga: Optional[Manga] = Relationship(back_populates="chapters")
    ocr_result: Optional["OCRResult"] = Relationship(back_populates="chapter")


class OCRResult(SQLModel, table=True):
    __tablename__ = "ocr_result"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chapter_id: UUID = Field(foreign_key="chapter.id", index=True, unique=True)
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


class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    __tablename__ = "user"

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    display_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)