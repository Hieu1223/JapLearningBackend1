from sqlmodel import SQLModel,Field
from uuid import UUID, uuid4
from pydantic import BaseModel
from typing import Optional

class QueryVRFToken(SQLModel, table= True):
    id : UUID = Field(primary_key=True, default_factory=uuid4)
    query : str = Field(index= True) 
    token : str = Field()

class Manga(SQLModel, table = True):
    id : UUID = Field(primary_key=True, default_factory=uuid4)
    manga_url : str = Field()
    manga_cover_url : str = Field()
    has_transcripted_chapters : bool = Field(default=False)

class Chapter(SQLModel, table = True):
    id : UUID = Field(primary_key=True, default_factory=uuid4)
    manga_id : UUID = Field(foreign_key='manga.id')
    num : int = Field()
    link : str = Field()
    title : str = Field()
    transcripted : bool = Field(default=False)
    

class Page(SQLModel, table = True):
    id : UUID = Field(primary_key=True, default_factory=uuid4)
    chapter_id : UUID = Field(foreign_key='chapter.id')
    image_url : str = Field()
    ocr_data : str = Field(default="")
    page_num : int = Field()


class ReadHistory(SQLModel, table = True):
    id : UUID = Field(primary_key=True, default_factory=uuid4)
    user_id : UUID = Field(foreign_key="user.id")
    manga_id : UUID = Field(foreign_key="manga.id")

