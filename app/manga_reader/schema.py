from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class MangaInfo(BaseModel):
    name : str
    cover_url : str
    manga_url : str


class MangaRequest(BaseModel):
    id : UUID

class MangaResponse(BaseModel):
    info : MangaInfo

class MangaFilterRequest(BaseModel):
    query : Optional[str]
    
class MangaFilterResponse(BaseModel):
    mangas : list[MangaInfo]

class MangaChapterRequest(BaseModel):
    manga_url : str 
