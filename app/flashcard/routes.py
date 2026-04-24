from fastapi import APIRouter, HTTPException, Depends
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
    CardSRDataResponse,
    ReviewRequest,
    AddCardRequest,
    UpdateCardRequest,
    DailyStatResponse,
    OverviewStatsResponse,
    PublicDeckResponse,
)

router = APIRouter()


# =========================================================
# PUBLIC DECK BROWSE
# =========================================================

@router.get("/decks/public", response_model=List[PublicDeckResponse])
def browse_public_decks(session: Session = Depends(get_session)):
    return FlashcardController.get_public_decks(session)


# =========================================================
# DECKS
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
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    deck = FlashcardController.create_deck(session, user_id, name, public)
    saved = FlashcardController.save_deck_for_user(session, user_id, deck.id)
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to save deck for user")
    decks = FlashcardController.list_decks_with_stats(session, user_id)
    # Return the newly created deck entry
    return next(d for d in decks if d.id == deck.id)


@router.patch("/decks/{deck_id}", response_model=DeckResponse)
def update_deck(
    deck_id: UUID,
    name: Optional[str] = None,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    updated = FlashcardController.update_deck(session, user_id, deck_id, name)
    if not updated:
        raise HTTPException(status_code=404, detail="Deck not found or not owned by user")
    return updated


@router.delete("/decks/{deck_id}")
def delete_deck(
    deck_id: UUID,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    if not FlashcardController.delete_deck(session, user_id, deck_id):
        raise HTTPException(status_code=404, detail="Deck not found or not owned by user")
    return {"success": True}


@router.post("/decks/{deck_id}/save")
def save_deck_for_user(
    deck_id: UUID,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    saved = FlashcardController.save_deck_for_user(session, user_id, deck_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Deck not found")
    return {"success": True, "user_saved_deck_id": saved.id}


@router.delete("/saved-decks/{user_saved_deck_id}")
def unsave_deck(
    user_saved_deck_id: UUID,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    if not FlashcardController.delete_saved_deck(session, user_id, user_saved_deck_id):
        raise HTTPException(status_code=404, detail="Saved deck not found or not owned by user")
    return {"success": True}


@router.get("/decks/{deck_id}/cards", response_model=List[CardResponse])
def get_cards_in_deck(
    deck_id: UUID,
    session: Session = Depends(get_session),
):
    return FlashcardController.list_cards(session, deck_id)


@router.get("/decks/{deck_id}/progress", response_model=DeckProgressResponse)
def get_deck_progress(
    deck_id: UUID,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    return FlashcardController.get_deck_progress(session, user_id, deck_id)


# =========================================================
# CARDS
# =========================================================

@router.post("/cards", response_model=CardResponse)
def create_card(
    req: AddCardRequest,
    session: Session = Depends(get_session),
):
    return FlashcardController.add_card_to_deck(session, req.deck_id, req.front)


@router.patch("/cards/{card_id}", response_model=CardResponse)
def update_card(
    card_id: UUID,
    req: UpdateCardRequest,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    """
    Update a card's front text (deck owner only).
    SR schedules are not affected — only the display text changes.
    """
    updated = FlashcardController.update_card(session, user_id, card_id, req.front)
    if not updated:
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return updated


@router.delete("/cards/{card_id}")
def delete_card(
    card_id: UUID,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    if not FlashcardController.delete_card(session, user_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return {"success": True}


@router.delete("/saved-decks/{user_saved_deck_id}/cards/{card_id}")
def delete_learned_card(
    user_saved_deck_id: UUID,
    card_id: UUID,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    """Remove a card's SR row from a saved deck so it resets to unseen."""
    if not FlashcardController.delete_learned_card(session, user_id, user_saved_deck_id, card_id):
        raise HTTPException(status_code=404, detail="SR record not found")
    return {"success": True}


# =========================================================
# SRS — next card & review
# =========================================================

@router.get("/cards/next", response_model=Optional[CardSRDataResponse])
def read_next_card(
    user_saved_deck_id: UUID,
    session: Session = Depends(get_session),
):
    """
    Fetch the next due card. If the deck has unseen cards and nothing is
    overdue, a new SR row is lazily created and returned as state=new.
    Returns null when there is nothing left to study.
    """
    return FlashcardController.fetch_due_card(session, user_saved_deck_id)


@router.post("/cards/review", response_model=CardSRDataResponse)
def review_card(
    req: ReviewRequest,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    """
    Submit a review rating. Applies SRS, writes a ReviewLog entry,
    and returns the updated SR record.
    """
    rating_map = {"again": 1, "hard": 2, "good": 3, "easy": 4}
    rating_int = rating_map.get(req.rating.lower())
    if rating_int is None:
        raise HTTPException(status_code=400, detail="Invalid rating")

    updated = FlashcardController.handle_review(session, user_id, req.sr_data_id, rating_int)
    if not updated:
        raise HTTPException(status_code=404, detail="SRS record not found")
    return updated


# =========================================================
# STATS
# =========================================================

@router.get("/stats/daily", response_model=List[DailyStatResponse])
def get_daily_stats(
    days: int = 30,
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    return FlashcardController.get_daily_stats(session, user_id, days)


@router.get("/stats/overview", response_model=OverviewStatsResponse)
def get_overview_stats(
    session: Session = Depends(get_session),
    user_id: CurrentUser = None,
):
    return FlashcardController.get_overview_stats(session, user_id)