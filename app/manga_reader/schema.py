from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class MangaInfo(BaseModel):
    name : str
    cover_url : str
    manga_url : str


class ChapterInfo(BaseModel):
    num : str
    title : str
    url : str

from pydantic import BaseModel, Field
from typing import List, Union

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

# The final output is usually a list of pages
class OCRResponse(BaseModel):
    pages: List[OCRPage]