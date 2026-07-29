"""
flashcard/routes.py
"""
from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session
from typing import List, Optional
from uuid import UUID

from ..security.auth import CurrentUser
from ..container import Container, get_db_session
from .schema import (
    DeckWithStatsResponse,
    DeckResponse,
    DeckProgressResponse,
    CardResponse,
    ReviewRequest,
    AddCardRequest,
    DailyStatResponse,
    OverviewStatsResponse,
    PublicDeckResponse,
)

router = APIRouter()

_container = Container()


@router.get("/decks/public", response_model=List[PublicDeckResponse])
def browse_public_decks():
    session = get_db_session()
    return _container.flashcard_service.get_public_decks(session)


@router.post("/decks/{deck_id}/copy", response_model=DeckWithStatsResponse)
def copy_public_deck(
    deck_id: UUID,
    user_id: CurrentUser,
):
    session = get_db_session()
    result = _container.flashcard_service.copy_deck(session, user_id, deck_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deck not found or is not public")
    return result


@router.get("/decks", response_model=List[DeckWithStatsResponse])
def read_decks(
    user_id: CurrentUser,
):
    session = get_db_session()
    return _container.flashcard_service.list_decks_with_stats(session, user_id)


@router.post("/decks", response_model=DeckWithStatsResponse)
def create_deck(
    name: str,
    public: bool = False,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    return _container.flashcard_service.create_deck(session, user_id, name, public)


@router.patch("/decks/{deck_id}", response_model=DeckResponse)
def update_deck(
    deck_id: UUID,
    name: str,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    updated = _container.flashcard_service.update_deck(session, user_id, deck_id, name)
    if not updated:
        raise HTTPException(status_code=404, detail="Deck not found or not owned by user")
    return updated


@router.delete("/decks/{deck_id}")
def delete_deck(
    deck_id: UUID,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    if not _container.flashcard_service.delete_deck(session, user_id, deck_id):
        raise HTTPException(status_code=404, detail="Deck not found or not owned by user")
    return {"success": True}


@router.get("/decks/{deck_id}/progress", response_model=DeckProgressResponse)
def get_deck_progress(
    deck_id: UUID,
):
    session = get_db_session()
    return _container.flashcard_service.get_deck_progress(session, deck_id)


@router.get("/decks/{deck_id}/cards", response_model=List[CardResponse])
def get_cards_in_deck(
    deck_id: UUID,
):
    session = get_db_session()
    return _container.flashcard_service.list_cards(session, deck_id)


@router.post("/cards", response_model=CardResponse)
def add_card(
    req: AddCardRequest,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    result = _container.flashcard_service.add_card(
        session=session,
        user_id=user_id,
        deck_id=req.deck_id,
        front=req.front,
        back=req.back,
    )
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Deck not found or not owned by user",
        )
    return result


@router.delete("/cards/{card_id}")
def delete_card(
    card_id: UUID,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    if not _container.flashcard_service.delete_card(session, user_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return {"success": True}


@router.post("/cards/{card_id}/reset")
def reset_card(
    card_id: UUID,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    if not _container.flashcard_service.reset_card(session, user_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return {"success": True}


@router.get("/decks/{deck_id}/next", response_model=Optional[CardResponse])
def read_next_card(
    deck_id: UUID,
):
    session = get_db_session()
    return _container.flashcard_service.fetch_due_card(session, deck_id)


@router.post("/cards/review", response_model=CardResponse)
def review_card(
    req: ReviewRequest,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    rating_map = {"again": 1, "hard": 2, "good": 3, "easy": 4}
    rating_int = rating_map.get(req.rating.lower())
    if rating_int is None:
        raise HTTPException(status_code=400, detail="Invalid rating")

    updated = _container.flashcard_service.handle_review(session, user_id, req.card_id, rating_int)
    if not updated:
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return updated


@router.get("/stats/daily", response_model=List[DailyStatResponse])
def get_daily_stats(
    days: int = 30,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    return _container.flashcard_service.get_daily_stats(session, user_id, days)


@router.get("/stats/overview", response_model=OverviewStatsResponse)
def get_overview_stats(
    user_id: CurrentUser = None,
):
    session = get_db_session()
    return _container.flashcard_service.get_overview_stats(session, user_id)