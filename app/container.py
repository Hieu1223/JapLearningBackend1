from typing import Callable
from sqlmodel import Session
from contextvars import ContextVar
import threading

_db_session_var: ContextVar[Session] = ContextVar('db_session')

_session_lock = threading.Lock()


class Container:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            with _session_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._services = {}
            self._initialized = True
    
    @classmethod
    def reset(cls):
        cls._instance = None
    
    def register(self, name: str, service):
        self._services[name] = service
    
    def get(self, name: str):
        return self._services.get(name)
    
    @property
    def transcription_service(self):
        if 'transcription' not in self._services:
            from .transcription.service import TranscriptionService
            self._services['transcription'] = TranscriptionService()
        return self._services['transcription']
    
    @property
    def flashcard_service(self):
        if 'flashcard' not in self._services:
            from .flashcard.service import FlashcardService
            self._services['flashcard'] = FlashcardService()
        return self._services['flashcard']
    
    @property
    def user_service(self):
        if 'user' not in self._services:
            from .user_management.service import UserService
            self._services['user'] = UserService()
        return self._services['user']
    
    @property
    def manga_reader_service(self):
        if 'manga_reader' not in self._services:
            from .manga_reader.service import MangaReaderService
            self._services['manga_reader'] = MangaReaderService()
        return self._services['manga_reader']
    
    @property
    def web_novel_service(self):
        if 'web_novel' not in self._services:
            from .web_novel.service import WebNovelService
            self._services['web_novel'] = WebNovelService()
        return self._services['web_novel']


def get_container() -> Container:
    return Container()


def set_db_session(session: Session):
    _db_session_var.set(session)


def get_db_session() -> Session:
    return _db_session_var.get()


def with_session(session: Session) -> Callable:
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            set_db_session(session)
            try:
                return func(*args, **kwargs)
            finally:
                _db_session_var.set(None)
        return wrapper
    return decorator