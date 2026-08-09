from typing import Annotated
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy import text
from fastapi import Depends
import os
from .user import User
from .transcription import Transcript,TranscriptionHistory
from .manga_reader import *
from .security import *




DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    _recreate_legacy_srscard()


def _recreate_legacy_srscard():
    """Recreate the srscard table if it still uses the old Anki schema.

    The SRS model was replaced with an fsrs-native schema (ts-fsrs Card
    fields). ``create_all`` never drops or alters existing tables, so if the
    legacy ``srscard`` (with ``queue``/``data`` Anki columns) is present we
    drop and recreate it from the current metadata. Existing scheduling data
    is Anki-format and incompatible, so it is discarded.
    """
    from .flashcard.schema import SrsCard

    with Session(engine) as session:
        has_legacy = session.exec(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'srscard' AND column_name = 'queue'"
        )).first()
        if not has_legacy:
            return

        session.exec(text("DROP TABLE srscard"))
        session.commit()
        SrsCard.metadata.create_all(engine, tables=[SrsCard.__table__])


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

