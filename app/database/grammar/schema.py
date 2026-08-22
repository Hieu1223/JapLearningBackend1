from typing import List, Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON


class ReibunItem(SQLModel):
    ja: str
    vn: str
    romaji: str


class Grammar(SQLModel, table=True):
    __tablename__ = "grammar"
    __table_args__ = {"extend_existing": True}

    id: int = Field(primary_key=True)
    keyword: str = Field(index=True)
    jp: str = Field()
    imi_setsumei: str = Field()
    tsukaikata_setsumei: str = Field()
    reibun: List[ReibunItem] = Field(sa_column=Column(JSON))
