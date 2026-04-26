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
    link : str = Field()
    transcripted : bool = Field(default=False)
    ocr_data : str = Field(default="")
    image_list : str = Field(default="{}")

from datetime import datetime , timezone

class ReadHistory(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    
    # Store manga details directly
    manga_url: str = Field(index=True) 
    
    current_chapter_url: str = Field(description="URL of the last chapter opened")
    current_chapter_name: Optional[str] = Field(default=None, description="e.g., 'Chapter 10'")
    
    read_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    
