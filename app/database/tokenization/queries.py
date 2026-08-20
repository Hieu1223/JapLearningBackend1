from .schema import *
from sqlmodel import Session, select
from uuid import UUID
from datetime import datetime, timezone
import json


def save_tokenization_history(
    session: Session,
    user_id: UUID,
    text: str,
    data_json: str | None,
    sentence_count: int,
) -> TokenizationHistory:
    entry = TokenizationHistory(
        user_id=user_id,
        text=text,
        data=data_json,
        sentences=sentence_count,
        date_created=datetime.now(timezone.utc),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def get_user_tokenization_history(
    session: Session, user_id: UUID, offset: int = 0, limit: int = 50
) -> list[TokenizationHistory]:
    return session.exec(
        select(TokenizationHistory)
        .where(TokenizationHistory.user_id == user_id)
        .order_by(TokenizationHistory.date_created.desc())
        .offset(offset)
        .limit(limit)
    ).all()


def delete_tokenization_history(
    session: Session, history_id: UUID, user_id: UUID
) -> bool:
    entry = session.exec(
        select(TokenizationHistory).where(
            TokenizationHistory.id == history_id,
            TokenizationHistory.user_id == user_id,
        )
    ).one_or_none()
    if not entry:
        return False
    session.delete(entry)
    session.commit()
    return True
