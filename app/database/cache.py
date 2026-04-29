from sqlmodel import SQLModel,Field,Session, select
from uuid import UUID,uuid4
from datetime import datetime

class CacheItem(SQLModel,table = True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    type_ : str
    extra_data : str
    created_at: datetime = Field(default_factory=datetime.utcnow)



def fetch_cache(session: Session, type_: str) -> CacheItem | None:
    stmt = select(CacheItem).where(CacheItem.type_ == type_)
    return session.exec(stmt).first()


def update_cache(session: Session, type_: str, extra_data: str) -> CacheItem:
    item = fetch_cache(session, type_)

    if item:
        item.extra_data = extra_data
        item.created_at = datetime.utcnow()
    else:
        item = CacheItem(
            type_=type_,
            extra_data=extra_data
        )
        session.add(item)

    session.commit()
    session.refresh(item)
    return item