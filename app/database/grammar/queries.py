from sqlmodel import Session, select
from .schema import Grammar


def search_grammar(
    session: Session, keyword: str, limit: int = 20
) -> list[Grammar]:
    pattern = f"%{keyword}%"
    return session.exec(
        select(Grammar)
        .where(Grammar.keyword.ilike(pattern))
        .order_by(Grammar.keyword)
        .limit(limit)
    ).all()
