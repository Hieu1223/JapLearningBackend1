"""
flashcard/routes.py
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlmodel import Session
from typing import List, Optional
from uuid import UUID

from ..database import get_session
from ..security.auth import CurrentUser
from .controller import FlashcardController
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
    WordResponse,
)
from ..tokenization.tokenize import get_or_fetch_words

router = APIRouter()


# =========================================================
# WORD SEARCH  (so the frontend can find word_ids to add)
# =========================================================

@router.get("/words/search", response_model=List[WordResponse])
async def search_words(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Full-text search across word, reading, and meaning."""
    return await get_or_fetch_words(session, q)


# =========================================================
# PUBLIC DECK BROWSE
# =========================================================

@router.get("/decks/public", response_model=List[PublicDeckResponse])
def browse_public_decks(session: Session = Depends(get_session)):
    return FlashcardController.get_public_decks(session)


@router.post("/decks/{deck_id}/copy", response_model=DeckWithStatsResponse)
def copy_public_deck(
    deck_id: UUID,
    user_id: CurrentUser,
    session: Session = Depends(get_session),
):
    """
    Deep-copy a public deck into the current user's account.
    Every card is cloned with fresh SR state.
    """
    result = FlashcardController.copy_deck(session, user_id, deck_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deck not found or is not public")
    return result


# =========================================================
# DECKS  (user's own)
# =========================================================

@router.get("/decks", response_model=List[DeckWithStatsResponse])
def read_decks(
    user_id: CurrentUser,
    session: Session = Depends(get_session),
):
    return FlashcardController.list_decks_with_stats(session, user_id)


@router.post("/decks", response_model=DeckWithStatsResponse)
def create_deck(
    name: str,
    public: bool = False,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return FlashcardController.create_deck(session, user_id, name, public)


@router.patch("/decks/{deck_id}", response_model=DeckResponse)
def update_deck(
    deck_id: UUID,
    name: str,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    updated = FlashcardController.update_deck(session, user_id, deck_id, name)
    if not updated:
        raise HTTPException(status_code=404, detail="Deck not found or not owned by user")
    return updated


@router.delete("/decks/{deck_id}")
def delete_deck(
    deck_id: UUID,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    if not FlashcardController.delete_deck(session, user_id, deck_id):
        raise HTTPException(status_code=404, detail="Deck not found or not owned by user")
    return {"success": True}


@router.get("/decks/{deck_id}/progress", response_model=DeckProgressResponse)
def get_deck_progress(
    deck_id: UUID,
    session: Session = Depends(get_session),
):
    return FlashcardController.get_deck_progress(session, deck_id)


# =========================================================
# CARDS
# =========================================================

@router.get("/decks/{deck_id}/cards", response_model=List[CardResponse])
def get_cards_in_deck(
    deck_id: UUID,
    session: Session = Depends(get_session),
):
    return FlashcardController.list_cards(session, deck_id)


@router.post("/cards", response_model=CardResponse)
def add_card(
    req: AddCardRequest,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """Add a word (by word_id) to one of the user's decks."""
    result = FlashcardController.add_card(session, user_id, req.deck_id, req.word_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Deck not found / not owned by user, or word_id does not exist",
        )
    return result


@router.delete("/cards/{card_id}")
def delete_card(
    card_id: UUID,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    if not FlashcardController.delete_card(session, user_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return {"success": True}


@router.post("/cards/{card_id}/reset")
def reset_card(
    card_id: UUID,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """Reset a card's SRS progress back to New state."""
    if not FlashcardController.reset_card(session, user_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return {"success": True}


# =========================================================
# SRS — next card & review
# =========================================================

@router.get("/decks/{deck_id}/next", response_model=Optional[CardResponse])
def read_next_card(
    deck_id: UUID,
    session: Session = Depends(get_session),
):
    """
    Fetch the next due card for a deck.
    Returns null when there is nothing left to study.
    """
    return FlashcardController.fetch_due_card(session, deck_id)


@router.post("/cards/review", response_model=CardResponse)
def review_card(
    req: ReviewRequest,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """Submit a review rating (again/hard/good/easy)."""
    rating_map = {"again": 1, "hard": 2, "good": 3, "easy": 4}
    rating_int = rating_map.get(req.rating.lower())
    if rating_int is None:
        raise HTTPException(status_code=400, detail="Invalid rating")

    updated = FlashcardController.handle_review(session, user_id, req.card_id, rating_int)
    if not updated:
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return updated


# =========================================================
# STATS
# =========================================================

@router.get("/stats/daily", response_model=List[DailyStatResponse])
def get_daily_stats(
    days: int = 30,
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return FlashcardController.get_daily_stats(session, user_id, days)


@router.get("/stats/overview", response_model=OverviewStatsResponse)
def get_overview_stats(
    user_id: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return FlashcardController.get_overview_stats(session, user_id)