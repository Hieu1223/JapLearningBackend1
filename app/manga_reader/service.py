import json
from uuid import UUID
from typing import Optional, AsyncIterator
from sqlmodel import Session
from fastapi import BackgroundTasks

from ..database.manga_reader.queries import (
    get_manga_list,
    search_manga,
    get_manga_by_id,
    get_chapter_by_id,
    get_chapters_for_manga,
    get_ocr_result_with_user,
    save_ocr_result,
    delete_ocr_result,
    get_read_histories,
    upsert_read_history,
    delete_read_history,
    delete_read_history_by_id,
)
from .schema import (
    OCRResponse,
    MangaPreview,
    MangaDetail,
    ChapterPreview,
    ReadResponse,
    OCRResultResponse,
    OCRUserInfo,
    ReadHistoryResponse,
)
from .manga_ocr import do_ocr_stream


def _manga_preview(manga) -> MangaPreview:
    return MangaPreview(
        id=manga.id,
        title=manga.title,
        cover=manga.cover,
        status=manga.status,
    )


def _chapter_preview(chapter) -> ChapterPreview:
    return ChapterPreview(
        id=chapter.id,
        title=chapter.title,
        chapter_index=chapter.chapter_index,
        date=chapter.date,
    )


def _expand_pages_to_urls(payload: dict) -> list[str]:
    t = payload.get("type")

    if t == "direct":
        return payload.get("images", [])

    if t == "template":
        base_url = payload["base_url"]
        page_count = payload["page_count"]
        pattern = payload["pattern"]
        return [f"{base_url}{pattern.format(i)}" for i in range(1, page_count + 1)]

    return []


class MangaReaderService:

    def get_manga_list(
        self,
        session: Session,
        query: Optional[str],
        limit: int,
        offset: int,
    ) -> list[MangaPreview]:
        if query:
            mangas = search_manga(session, query, limit, offset)
        else:
            mangas = get_manga_list(session, limit, offset)
        return [_manga_preview(m) for m in mangas]

    def get_manga_detail(self, session: Session, manga_id: UUID) -> Optional[MangaDetail]:
        manga = get_manga_by_id(session, manga_id)
        if not manga:
            return None

        chapters = get_chapters_for_manga(session, manga_id)

        return MangaDetail(
            id=manga.id,
            title=manga.title,
            cover=manga.cover,
            status=manga.status,
            description=manga.description,
            genres=manga.genres,
            chapters=[_chapter_preview(c) for c in chapters],
        )

    def read_chapter(self, session: Session, chapter_id: UUID) -> Optional[ReadResponse]:
        chapter = get_chapter_by_id(session, chapter_id)
        if not chapter:
            return None

        manga = get_manga_by_id(session, chapter.manga_id)
        if not manga:
            return None

        chapters = get_chapters_for_manga(session, manga.id)

        payload = json.loads(chapter.pages) if chapter.pages else {"type": "empty"}
        pages = _expand_pages_to_urls(payload)

        return ReadResponse(
            manga=_manga_preview(manga),
            chapter=_chapter_preview(chapter),
            chapters=[_chapter_preview(c) for c in chapters],
            pages=pages,
        )

    def get_existing_ocr(
        self,
        session: Session,
        chapter_id: UUID,
    ) -> Optional[OCRResultResponse]:
        row = get_ocr_result_with_user(session, chapter_id)
        if not row:
            return None

        ocr_result, user = row

        chapter = get_chapter_by_id(session, chapter_id)
        if not chapter:
            return None

        manga = get_manga_by_id(session, chapter.manga_id)
        if not manga:
            return None

        return OCRResultResponse(
            chapter_id=chapter_id,
            ocr_date=ocr_result.ocr_date,
            ocr_by=OCRUserInfo(id=user.id, display_name=user.display_name) if user else None,
            manga=_manga_preview(manga),
            ocr_data=OCRResponse.model_validate(json.loads(ocr_result.ocr_data)),
        )

    async def stream_ocr(
        self,
        session: Session,
        chapter_id: UUID,
        user_id: UUID,
        background_tasks: BackgroundTasks,
    ) -> AsyncIterator[str]:
        chapter = get_chapter_by_id(session, chapter_id)
        if not chapter or not chapter.pages:
            raise ValueError("Chapter has no pages to OCR")

        payload = json.loads(chapter.pages)
        image_urls = _expand_pages_to_urls(payload)

        if not image_urls:
            raise ValueError("Chapter has no pages to OCR")

        accumulated: list[dict] = []

        def _save_to_db():
            save_ocr_result(
                session,
                chapter_id=chapter_id,
                ocr_data=json.dumps({"pages": accumulated}),
                ocr_by=user_id,
            )

        background_tasks.add_task(_save_to_db)

        async for page in do_ocr_stream(image_urls):
            accumulated.append(page)
            yield f"data: {json.dumps(page)}\n\n"

        yield "data: [DONE]\n\n"

    def get_history(self, session: Session, user_id: UUID) -> list[ReadHistoryResponse]:
        rows = get_read_histories(session, user_id)
        return [
            ReadHistoryResponse(
                id=row.id,
                current_page=row.current_page,
                updated_at=row.updated_at,
                manga_id=row.manga_id,
                manga_title=row.manga_title,
                manga_cover=row.manga_cover,
                chapter_id=row.chapter_id,
                chapter_index=row.chapter_index,
            )
            for row in rows
        ]

    def upsert_history(
        self,
        session: Session,
        user_id: UUID,
        manga_id: UUID,
        chapter_id: UUID,
        current_page: int,
    ) -> ReadHistoryResponse:
        manga = get_manga_by_id(session, manga_id)
        if not manga:
            raise ValueError("Manga not found")

        chapter = get_chapter_by_id(session, chapter_id)
        if not chapter:
            raise ValueError("Chapter not found")

        history = upsert_read_history(session, user_id, manga_id, chapter_id, current_page)

        return ReadHistoryResponse(
            id=history.id,
            current_page=history.current_page,
            updated_at=history.updated_at,
            manga_id=manga.id,
            manga_title=manga.title,
            manga_cover=manga.cover,
            chapter_id=chapter.id,
            chapter_index=chapter.chapter_index,
        )

    def delete_history(self, session: Session, user_id: UUID, manga_id: UUID):
        return delete_read_history(session, user_id, manga_id)

    def delete_history_by_id(self, session: Session, user_id: UUID, history_id: UUID):
        return delete_read_history_by_id(session, history_id, user_id)

    def reset_ocr(self, session: Session, chapter_id: UUID) -> bool:
        return delete_ocr_result(session, chapter_id)