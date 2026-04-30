from pydantic import BaseModel
from typing import Optional, List, Union
from uuid import UUID
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────────────────────

class OCRBlock(BaseModel):
    # box is [x1, y1, x2, y2]
    box: List[int]
    vertical: bool
    font_size: float
    # lines_coords is a list of 4 points, each point is [x, y]
    lines_coords: List[List[List[float]]]
    lines: List[str]


class OCRPage(BaseModel):
    version: str
    img_width: int
    img_height: int
    blocks: List[OCRBlock]


class OCRResponse(BaseModel):
    pages: List[OCRPage]


# ─────────────────────────────────────────────────────────────
# PAGES PAYLOAD
# ─────────────────────────────────────────────────────────────

class PagesPayloadEmpty(BaseModel):
    type: str = "empty"


class PagesPayloadTemplate(BaseModel):
    type: str = "template"
    base_url: str
    page_count: int
    pattern: str


class PagesPayloadDirect(BaseModel):
    type: str = "direct"
    images: List[str]


PagesPayload = Union[PagesPayloadEmpty, PagesPayloadTemplate, PagesPayloadDirect]


# ─────────────────────────────────────────────────────────────
# MANGA
# ─────────────────────────────────────────────────────────────

class ChapterPreview(BaseModel):
    id: UUID
    title: str
    chapter_index: Optional[int]
    date: Optional[str]

    class Config:
        from_attributes = True


class MangaPreview(BaseModel):
    id: UUID
    title: str
    cover: Optional[str]
    status: Optional[str]

    class Config:
        from_attributes = True


class MangaDetail(BaseModel):
    id: UUID
    title: str
    cover: Optional[str]
    status: Optional[str]
    description: Optional[str]
    genres: Optional[str]
    chapters: List[ChapterPreview]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────────────────────

class ReadResponse(BaseModel):
    manga: MangaPreview
    chapter: ChapterPreview
    chapters: List[ChapterPreview]
    pages: List[str]


# ─────────────────────────────────────────────────────────────
# OCR RESULT
# ─────────────────────────────────────────────────────────────

class OCRUserInfo(BaseModel):
    id: UUID
    display_name: Optional[str]

    class Config:
        from_attributes = True


class OCRResultResponse(BaseModel):
    chapter_id: UUID
    ocr_date: datetime
    ocr_by: Optional[OCRUserInfo]
    manga: MangaPreview
    ocr_data: OCRResponse


# ─────────────────────────────────────────────────────────────
# HISTORY
# ─────────────────────────────────────────────────────────────

class ReadHistoryUpdate(BaseModel):
    manga_id: UUID
    chapter_id: UUID
    current_page: int = 0


class ReadHistoryResponse(BaseModel):
    id: UUID
    current_page: int
    updated_at: datetime

    manga_id: UUID
    manga_title: str
    manga_cover: Optional[str]

    chapter_id: UUID
    chapter_index: Optional[int]

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────

class MangaSearchQuery(BaseModel):
    q: str
    limit: int = 20
    offset: int = 0