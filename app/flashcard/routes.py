from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from typing import List, Optional
from uuid import UUID

from ..database import get_session
from .controller import FlashcardController
from .schema import (
    DeckResponse, 
    CardResponse, 
    ReviewRequest, 
    AddCardRequest, 
    CardSRDataResponse
)
router = APIRouter()

@router.get("/decks", response_model=List[DeckResponse])
def read_decks(
    user_id: UUID, 
    session: Session = Depends(get_session)
):
    """Returns all decks saved by the user with their SRS stats."""
    return FlashcardController.list_decks_with_stats(session, user_id)

@router.get("/cards/next", response_model=Optional[CardResponse])
def read_next_card(
    user_saved_deck_id: UUID, 
    session: Session = Depends(get_session)
):
    """Fetches the single most urgent card for a specific saved deck."""
    result = FlashcardController.fetch_due_card(session, user_saved_deck_id)
    if not result:
        return None
    card, _ = result
    return card

@router.post("/cards/review", response_model=CardSRDataResponse)
def review_card(
    req: ReviewRequest, 
    session: Session = Depends(get_session)
):
    """Processes a card review using FSRS and returns the updated spacing data."""
    # Mapping string literal to FSRS int (1: Again, 2: Hard, 3: Good, 4: Easy)
    rating_map = {"again": 1, "hard": 2, "good": 3, "easy": 4}
    rating_int = rating_map.get(req.rating.lower())
    
    updated_sr = FlashcardController.handle_review(
        session, 
        req.sr_data_id, 
        rating_int
    )
    
    if not updated_sr:
        raise HTTPException(status_code=404, detail="SRS record not found")
    return updated_sr

@router.post("/cards", response_model=CardResponse)
def create_card(
    req: AddCardRequest, 
    session: Session = Depends(get_session)
):
    """Adds a new card to a deck using the query layer."""
    return FlashcardController.add_card_to_deck(
        session, 
        deck_id=req.deck_id, 
        front=req.front, 
        back=req.back
    )