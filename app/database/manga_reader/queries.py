from sqlmodel import Session
from uuid import UUID
from .schema import Manga, Chapter,Page

def get_cached_search_vrf_token(session : Session, query: str) -> str | None:
    return None

def update_cached_search_vrf_token(session: Session, query: str,vrf_token: str):
    a = 1

def get_cached_manga_info(session:Session, manga_urls : str) -> list[Manga]:
    pass

def update_mangas_info(session:Session, mangas: list[Manga]):
    pass

def add_chapter_infos(session : Session, chapters : list[Chapter]):
    pass

def get_cached_chapter_info(session:Session, chapter_url: str):
    pass

def update_chapter_pages(session : Session, chapter_id: UUID ,pages: list[Page]):
    pass

def get_cached_pages(session : Session, chapter_id : UUID) -> list[Page]:
    pass

def get_read_histories(session:Session, user_id : UUID) -> list[Manga]:
    pass