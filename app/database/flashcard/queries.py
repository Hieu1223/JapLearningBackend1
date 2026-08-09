"""
database/flashcard/queries.py
"""

from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List

from sqlmodel import Session, select, func, col

from .schema import Card, Deck, SrsCard, CardType


def add_deck(session: Session, user_id: UUID, name: str, public: bool = False) -> Deck:
    deck = Deck(name=name, owner_id=user_id, public=public)
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return deck


def get_deck_by_id(session: Session, deck_id: UUID) -> Optional[Deck]:
    return session.get(Deck, deck_id)


def get_decks_for_user(session: Session, user_id: UUID) -> List[Deck]:
    return session.exec(select(Deck).where(Deck.owner_id == user_id)).all()


def update_deck(session: Session, user_id: UUID, deck_id: UUID, name: str) -> Optional[Deck]:
    deck = session.get(Deck, deck_id)
    if not deck or deck.owner_id != user_id:
        return None
    deck.name = name
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return deck


def delete_deck(session: Session, user_id: UUID, deck_id: UUID) -> bool:
    deck = session.get(Deck, deck_id)
    if not deck or deck.owner_id != user_id:
        return False
    for card in session.exec(select(Card).where(Card.deck_id == deck_id)).all():
        srs = get_srs_card(session, card.id)
        if srs:
            session.delete(srs)
        session.delete(card)
    session.delete(deck)
    session.commit()
    return True


def get_public_decks(session: Session) -> List[tuple]:
    rows = session.exec(
        select(Deck, func.count(Card.id).label("card_count"))
        .outerjoin(Card, Card.deck_id == Deck.id)
        .where(Deck.public == True)
        .group_by(Deck.id)
    ).all()
    return rows


def copy_deck_for_user(session: Session, user_id: UUID, source_deck_id: UUID) -> Optional[Deck]:
    source = session.get(Deck, source_deck_id)
    if not source or not source.public:
        return None

    new_deck = Deck(name=source.name, owner_id=user_id, public=False)
    session.add(new_deck)
    session.flush()

    source_cards = session.exec(select(Card).where(Card.deck_id == source_deck_id)).all()
    for src_card in source_cards:
        clone = Card(
            deck_id=new_deck.id,
            data=src_card.data,
            card_type=src_card.card_type,
        )
        session.add(clone)
        session.flush()
        create_srs_card(session, clone.id, new_deck.id)

    session.commit()
    session.refresh(new_deck)
    return new_deck


def get_cards_by_deck(session: Session, deck_id: UUID) -> List[Card]:
    return session.exec(
        select(Card).where(Card.deck_id == deck_id)
    ).all()


def add_card_to_deck(session: Session, deck_id: UUID, data: str, card_type: CardType, sorting_id: str) -> Card:
    card = Card(deck_id=deck_id, data=data, card_type=card_type, sorting_id=sorting_id)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def delete_card(session: Session, user_id: UUID, card_id: UUID) -> bool:
    card = session.get(Card, card_id)
    if not card:
        return False
    deck = session.get(Deck, card.deck_id)
    if not deck or deck.owner_id != user_id:
        return False
    srs = get_srs_card(session, card_id)
    if srs:
        session.delete(srs)
    session.delete(card)
    session.commit()
    return True


def reset_card(session: Session, user_id: UUID, card_id: UUID) -> bool:
    card = session.get(Card, card_id)
    if not card:
        return False
    deck = session.get(Deck, card.deck_id)
    if not deck or deck.owner_id != user_id:
        return False

    # Reset to a brand-new FSRS card (state=New, no memory state yet).
    srs = get_srs_card(session, card_id)
    if srs:
        srs.due = datetime.utcnow()
        srs.stability = 0.0
        srs.difficulty = 0.0
        srs.elapsed_days = 0
        srs.scheduled_days = 0
        srs.learning_steps = 0
        srs.reps = 0
        srs.lapses = 0
        srs.state = 0  # New
        srs.last_review = None
        session.add(srs)

    session.commit()
    return True


def get_card_by_id(session: Session, card_id: UUID) -> Optional[Card]:
    return session.get(Card, card_id)


def get_review_session(session: Session, deck_id: UUID, limit: int = 20) -> List[Card]:
    now = datetime.utcnow()
    stmt = (
        select(Card)
        .join(SrsCard, SrsCard.card_id == Card.id)
        .where(Card.deck_id == deck_id)
        .where(SrsCard.due <= now)
        .order_by(SrsCard.due)
        .limit(limit)
    )
    return session.exec(stmt).all()


def get_srs_card(session: Session, card_id: UUID) -> Optional[SrsCard]:
    """Get SRS data for a card."""
    return session.exec(
        select(SrsCard).where(SrsCard.card_id == card_id)
    ).first()


def create_srs_card(session: Session, card_id: UUID, deck_id: UUID, now: datetime = None) -> SrsCard:
    """Create a brand-new FSRS card (state=New) for a card."""
    if now is None:
        now = datetime.utcnow()

    srs = SrsCard(
        card_id=card_id,
        due=now,
        stability=0.0,
        difficulty=0.0,
        elapsed_days=0,
        scheduled_days=0,
        learning_steps=0,
        reps=0,
        lapses=0,
        state=0,  # New
        last_review=None,
    )
    session.add(srs)
    session.commit()
    session.refresh(srs)
    return srs


def update_srs_card(session: Session, srs: SrsCard, **updates) -> SrsCard:
    """Update FSRS fields on a card."""
    for k, v in updates.items():
        setattr(srs, k, v)
    session.add(srs)
    session.commit()
    session.refresh(srs)
    return srs


def get_due_cards(session: Session, deck_id: UUID, limit: int = 20) -> List[Card]:
    """Get cards that are due/overdue for review.

    A card is due when its ``due`` timestamp is in the past. This covers
    New cards (due immediately), Learning/Relearning cards whose next step
    has been reached, and Review cards that are overdue.
    """
    now = datetime.utcnow()

    stmt = (
        select(Card)
        .join(SrsCard, SrsCard.card_id == Card.id)
        .where(Card.deck_id == deck_id)
        .where(SrsCard.due <= now)
        .order_by(SrsCard.due)
        .limit(limit)
    )
    return session.exec(stmt).all()


def get_deck_srs_stats(session: Session, deck_id: UUID) -> dict:
    """Get deck statistics: new, learning, and due (overdue) card counts."""
    now = datetime.utcnow()

    total = session.exec(
        select(func.count(Card.id))
        .join(SrsCard, SrsCard.card_id == Card.id)
        .where(Card.deck_id == deck_id)
    ).one() or 0

    state_rows = session.exec(
        select(SrsCard.state, func.count(SrsCard.id))
        .join(Card, Card.id == SrsCard.card_id)
        .where(Card.deck_id == deck_id)
        .group_by(SrsCard.state)
    ).all()

    stats = {"total": total, "new": 0, "learning": 0, "due": 0}
    state_map = {0: "new", 1: "learning"}
    for state, count in state_rows:
        key = state_map.get(state)
        if key:
            stats[key] = count

    # ``due`` = number of cards whose due timestamp is in the past (overdue),
    # regardless of their FSRS state.
    stats["due"] = session.exec(
        select(func.count(Card.id))
        .join(SrsCard, SrsCard.card_id == Card.id)
        .where(Card.deck_id == deck_id)
        .where(SrsCard.due <= now)
    ).one() or 0

    return stats


def get_all_deck_srs_stats_for_user(session: Session, user_id: UUID) -> dict:
    """Get all deck stats for a user: new, learning, and due (overdue) counts."""
    now = datetime.utcnow()

    decks = session.exec(select(Deck).where(Deck.owner_id == user_id)).all()
    if not decks:
        return {}

    result = {
        d.id: {"new": 0, "learning": 0, "due": 0, "total": 0}
        for d in decks
    }

    for deck_id, cnt in session.exec(
        select(Card.deck_id, func.count(Card.id))
        .join(SrsCard, SrsCard.card_id == Card.id)
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .group_by(Card.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["total"] = cnt

    state_map = {0: "new", 1: "learning"}
    for deck_id, state, cnt in session.exec(
        select(Card.deck_id, SrsCard.state, func.count(SrsCard.id))
        .join(SrsCard, SrsCard.card_id == Card.id)
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .group_by(Card.deck_id, SrsCard.state)
    ).all():
        if deck_id in result:
            key = state_map.get(state)
            if key:
                result[deck_id][key] = cnt

    for deck_id, due_cnt in session.exec(
        select(Card.deck_id, func.count(Card.id))
        .join(SrsCard, SrsCard.card_id == Card.id)
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .where(SrsCard.due <= now)
        .group_by(Card.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["due"] = due_cnt

    return result


