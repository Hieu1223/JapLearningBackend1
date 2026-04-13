from typing import Annotated
from sqlmodel import Session, SQLModel, create_engine, select
from fastapi import Depends
import os
from .user import User
from .transcription import Transcript,TranscriptionHistory





DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

