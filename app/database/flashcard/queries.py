from uuid import UUID
from datetime import datetime
from typing import Optional, List, Tuple
from sqlmodel import Session, select, func, and_
from .schema import Card, CardSRData, Deck, UserSavedDeck, State

# --- DECK & CARD MANAGEMENT ---

def add_deck(session: Session, user_id: UUID, name: str, public: bool = False) -> Deck:
    deck = Deck(name=name, owner_id=user_id, public=public)
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return deck

def add_card_to_deck(session: Session, deck_id: UUID, front: str, back: str) -> Card:
    card = Card(deck_id=deck_id, front=front, back=back)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card

# --- USER SAVED DECK LOGIC ---

def get_user_saved_decks(session: Session, user_id: UUID) -> List[Tuple[UserSavedDeck, Deck]]:
    """Fetches all decks a user has joined."""
    statement = (
        select(UserSavedDeck, Deck)
        .join(Deck, UserSavedDeck.deck_id == Deck.id)
        .where(UserSavedDeck.user_id == user_id)
    )
    return session.exec(statement).all()

def save_deck_for_user(session: Session, user_id: UUID, deck_id: UUID) -> UserSavedDeck:
    saved_deck = UserSavedDeck(user_id=user_id, deck_id=deck_id)
    session.add(saved_deck)
    session.commit()
    session.refresh(saved_deck)
    bulk_init_sr_data(session, saved_deck.id)
    return saved_deck

# --- SRS QUERIES ---

def get_sr_data_by_id(session: Session, sr_data_id: UUID) -> Optional[CardSRData]:
    return session.get(CardSRData, sr_data_id)

def get_next_card(session: Session, user_saved_deck_id: UUID) -> Optional[Tuple[Card, CardSRData]]:
    statement = (
        select(Card, CardSRData)
        .join(CardSRData, Card.id == CardSRData.card_id)
        .where(CardSRData.user_saved_deck_id == user_saved_deck_id)
        .where(CardSRData.due <= datetime.utcnow())
        .order_by(CardSRData.due)
    )
    return session.exec(statement).first()

def update_card_sr(session: Session, sr_data_id: UUID, **updates) -> Optional[CardSRData]:
    sr_data = session.get(CardSRData, sr_data_id)
    if sr_data:
        for key, value in updates.items():
            setattr(sr_data, key, value)
        session.add(sr_data)
        session.commit()
        session.refresh(sr_data)
    return sr_data

def get_deck_inventory_stats(session: Session, user_saved_deck_id: UUID) -> List[Tuple[State, int]]:
    statement = (
        select(CardSRData.state, func.count(CardSRData.id))
        .where(CardSRData.user_saved_deck_id == user_saved_deck_id)
        .group_by(CardSRData.state)
    )
    return session.exec(statement).all()

def bulk_init_sr_data(session: Session, user_saved_deck_id: UUID):
    saved_deck = session.get(UserSavedDeck, user_saved_deck_id)
    if not saved_deck:
        return
    subquery = select(CardSRData.card_id).where(CardSRData.user_saved_deck_id == user_saved_deck_id)
    new_cards = session.exec(
        select(Card).where(and_(Card.deck_id == saved_deck.deck_id, Card.id.not_in(subquery)))
    ).all()
    for card in new_cards:
        session.add(CardSRData(user_saved_deck_id=user_saved_deck_id, card_id=card.id, due=datetime.utcnow()))
    session.commit()