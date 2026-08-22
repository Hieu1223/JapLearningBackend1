import json
from uuid import UUID
from typing import Optional, AsyncIterator
from sqlmodel import Session, select
from datetime import datetime, timezone
from fastapi import BackgroundTasks

from ..database.manga_reader.queries import (
    get_manga_list,
    search_manga,
    get_manga_by_id,
    get_manga_creators,
    get_chapter_by_id,
    get_chapters_for_manga,
    list_genres,
    list_genres_by_ids,
    list_creators,
    get_ocr_result_with_user,
    save_ocr_page,
    delete_ocr_result,
    get_read_histories,
    upsert_read_history,
    delete_read_history,
    delete_read_history_by_id,
)
from ..database.user.schema import User
from .schema import (
    OCRResponse,
    OCRPage,
    MangaPreview,
    MangaDetail,
    CreatorPreview,
    GenrePreview,
    ChapterPreview,
    ReadResponse,
    OCRResultResponse,
    OCRUserInfo,
    ReadHistoryResponse,
)
from .manga_ocr import do_ocr_stream, analyze_ocr_page


def _manga_preview(manga, session: Session) -> MangaPreview:
    return MangaPreview(
        id=manga.id,
        title=manga.title,
        cover=manga.cover,
        status=manga.status,
        alternative_title=manga.alternative_title,
        description=manga.description,
        genres=[_genre_preview(g) for g in list_genres_by_ids(session, manga.genre_ids or [])],
        score=manga.score,
        views_weekly=manga.views_weekly,
        reader_count=manga.reader_count,
        updated_at=manga.updated_at,
    )


def _chapter_preview(chapter) -> ChapterPreview:
    return ChapterPreview(
        id=chapter.id,
        title=chapter.title,
        chapter_index=chapter.chapter_index,
        date=chapter.date,
    )


def _creator_preview(creator) -> CreatorPreview:
    return CreatorPreview(
        id=creator.id,
        source_term_id=creator.source_term_id,
        slug=creator.slug,
        name=creator.name,
        role=creator.role,
    )


def _genre_preview(genre) -> GenrePreview:
    return GenrePreview(
        id=genre.id,
        slug=genre.slug,
        name=genre.name,
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
        tags: Optional[list[str]] = None,
        author: Optional[UUID] = None,
        order_by: Optional[str] = None,
        order_dir: str = "desc",
    ) -> list[MangaPreview]:
        if query:
            mangas = search_manga(session, query, limit, offset, tags=tags, author=author, order_by=order_by, order_dir=order_dir)
        else:
            mangas = get_manga_list(session, limit, offset, tags=tags, author=author, order_by=order_by, order_dir=order_dir)
        return [_manga_preview(m, session) for m in mangas]

    def get_genres(
        self,
        session: Session,
        q: Optional[str] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GenrePreview]:
        genres = list_genres(session, q=q, order_by=order_by, limit=limit, offset=offset)
        return [_genre_preview(g) for g in genres]

    def get_creators(
        self,
        session: Session,
        q: Optional[str] = None,
        role: Optional[str] = None,
        order_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CreatorPreview]:
        creators = list_creators(session, q=q, role=role, order_by=order_by, limit=limit, offset=offset)
        return [_creator_preview(c) for c in creators]

    def get_manga_detail(self, session: Session, manga_id: UUID) -> Optional[MangaDetail]:
        manga = get_manga_by_id(session, manga_id)
        if not manga:
            return None

        chapters = get_chapters_for_manga(session, manga_id)
        creators = get_manga_creators(session, manga_id)

        return MangaDetail(
            id=manga.id,
            title=manga.title,
            cover=manga.cover,
            status=manga.status,
            alternative_title=manga.alternative_title,
            description=manga.description,
            description_native=manga.description_native,
            manga_type=manga.manga_type,
            genres=[_genre_preview(g) for g in list_genres_by_ids(session, manga.genre_ids or [])],
            released=manga.released,
            serialization=manga.serialization,
            score=manga.score,
            views_daily=manga.views_daily,
            views_weekly=manga.views_weekly,
            views_monthly=manga.views_monthly,
            reader_count=manga.reader_count,
            published_at=manga.published_at,
            updated_at=manga.updated_at,
            creators=[_creator_preview(c) for c in creators],
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
            manga=_manga_preview(manga, session),
            chapter=_chapter_preview(chapter),
            chapters=[_chapter_preview(c) for c in chapters],
            pages=pages,
        )

    def get_existing_ocr(
        self,
        session: Session,
        chapter_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> Optional[OCRResultResponse]:
        row = get_ocr_result_with_user(session, chapter_id, offset, limit)
        if not row:
            return None

        window, ocr_by = row
        user = session.get(User, ocr_by) if ocr_by else None

        all_pages = [json.loads(p.ocr_data) for p in window]
        total_pages = session.exec(
            select(OCRResult).where(OCRResult.chapter_id == chapter_id)
        ).count()

        return OCRResultResponse(
            chapter_id=chapter_id,
            ocr_date=window[-1].ocr_date if window else datetime.now(timezone.utc),
            ocr_by=OCRUserInfo(id=user.id, display_name=user.display_name) if user else None,
            ocr_data=OCRResponse(pages=[OCRPage.model_validate(p) for p in all_pages]),
            total_pages=total_pages,
            offset=offset,
            limit=limit,
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

        accumulated: list[tuple[int, dict]] = []

        def _save_to_db():
            for page_number, analyzed in accumulated:
                save_ocr_page(
                    session,
                    chapter_id=chapter_id,
                    page_number=page_number,
                    ocr_data=json.dumps(analyzed),
                    ocr_by=user_id,
                )

        background_tasks.add_task(_save_to_db)

        async for idx, page in enumerate(do_ocr_stream(image_urls)):
            analyzed = analyze_ocr_page(page)
            accumulated.append((idx, analyzed.model_dump()))
            yield f"data: {json.dumps(analyzed.model_dump())}\n\n"

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