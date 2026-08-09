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
    CardWithSrsResponse,
    SaveReviewRequest,
    ReviewSessionResponse,
    ReviewSessionWithSrsResponse,
    AddVocabRequest,
    PublicDeckResponse,
)

router = APIRouter()

_container = Container()


@router.get("/decks/public", response_model=List[PublicDeckResponse], tags=["Decks"], description="Return every deck that has been shared publicly so the caller can browse and choose one to copy into their own collection")
def browse_public_decks():
    session = get_db_session()
    return _container.flashcard_service.get_public_decks(session)


@router.post("/decks/{deck_id}/copy", response_model=DeckWithStatsResponse, tags=["Decks"], description="Clone a public deck, including all of its cards and their SRS scheduling data, into a fresh private deck owned by the current user")
def copy_public_deck(
    deck_id: UUID,
    user_id: CurrentUser,
):
    session = get_db_session()
    result = _container.flashcard_service.copy_deck(session, user_id, deck_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deck not found or is not public")
    return result


@router.get("/decks", response_model=List[DeckWithStatsResponse], tags=["Decks"], description="List every deck belonging to the current user, each enriched with live SRS counts (new, learning and due cards)")
def read_decks(
    user_id: CurrentUser,
):
    session = get_db_session()
    return _container.flashcard_service.list_decks_with_stats(session, user_id)


@router.post("/decks", response_model=DeckWithStatsResponse, tags=["Decks"], description="Create a new, empty flashcard deck for the current user, optionally marking it public so others can copy it")
def create_deck(
    name: str,
    public: bool = False,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    return _container.flashcard_service.create_deck(session, user_id, name, public)


@router.patch("/decks/{deck_id}", response_model=DeckResponse, tags=["Decks"], description="Rename an existing deck; only the deck's owner may change its name")
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


@router.delete("/decks/{deck_id}", tags=["Decks"], description="Permanently delete a deck along with all of its cards and their associated SRS scheduling records")
def delete_deck(
    deck_id: UUID,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    if not _container.flashcard_service.delete_deck(session, user_id, deck_id):
        raise HTTPException(status_code=404, detail="Deck not found or not owned by user")
    return {"success": True}


@router.get("/decks/{deck_id}/progress", response_model=DeckProgressResponse, tags=["Decks"], description="Compute the current SRS progress for a deck, reporting how many cards are new, in learning, and due for study")
def get_deck_progress(
    deck_id: UUID,
):
    session = get_db_session()
    return _container.flashcard_service.get_deck_progress(session, deck_id)


@router.get("/decks/{deck_id}/cards", response_model=List[CardResponse], tags=["Cards"], description="Return all cards in a deck together with their derived SRS state (new, learning, review or relearning) and scheduling info")
def get_cards_in_deck(
    deck_id: UUID,
):
    session = get_db_session()
    return _container.flashcard_service.list_cards(session, deck_id)


@router.post("/decks/{deck_id}/cards/vocab", response_model=CardResponse, tags=["Cards"], description="Add a vocabulary card to a deck by supplying the word and its meaning; the card is stored as a vocab card with a sorting id of the form <word>-vocab for ordering and duplicate detection, and its initial SRS scheduling data is seeded")
def add_vocab(
    deck_id: UUID,
    req: AddVocabRequest,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    result = _container.flashcard_service.add_vocab(
        session=session,
        user_id=user_id,
        deck_id=deck_id,
        word=req.word,
        meaning=req.meaning,
    )
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Deck not found or not owned by user",
        )
    return result


@router.delete("/decks/{deck_id}/cards/{card_id}", tags=["Cards"], description="Remove a single card and its SRS scheduling record from its deck")
def delete_card(
    deck_id: UUID,
    card_id: UUID,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    if not _container.flashcard_service.delete_card(session, user_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return {"success": True}


@router.post("/decks/{deck_id}/cards/{card_id}/reset", tags=["Cards"], description="Reset a card's SRS data back to a brand-new state so it re-enters the learning queue from scratch")
def reset_card(
    deck_id: UUID,
    card_id: UUID,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    if not _container.flashcard_service.reset_card(session, user_id, card_id):
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return {"success": True}


@router.get("/decks/{deck_id}/review-session", response_model=ReviewSessionWithSrsResponse, tags=["Reviews"], description="Load the next batch of cards in a deck that are due for review (new, learning, relearning or review-past-due) with their raw FSRS scheduling fields")
def load_review_session(
    deck_id: UUID,
    limit: int = Query(20, ge=1, le=100),
):
    session = get_db_session()
    result = _container.flashcard_service.load_review_session_with_srs(session, deck_id, limit)
    return result


@router.post("/cards/{card_id}/review", response_model=CardResponse, tags=["Reviews"], description="Persist the ts-fsrs Card object computed by the frontend scheduler for a card and return the card with its new state")
def review_card(
    card_id: UUID,
    req: SaveReviewRequest,
    user_id: CurrentUser = None,
):
    session = get_db_session()
    updated = _container.flashcard_service.save_review(
        session,
        user_id,
        card_id,
        card=req.card,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Card not found or not owned by user")
    return updated
