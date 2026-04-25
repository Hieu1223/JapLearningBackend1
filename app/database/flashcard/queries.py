"""
database/flashcard/queries.py
"""

from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlmodel import Session, select, func, case, col

from .schema import Card, Deck, ReviewLog, State
from ..dictionary.schema import Word, Kanji, WordKanjiReading

# =========================================================
# DECK
# =========================================================

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
    """Deletes the deck and all its cards (including SR data and review logs)."""
    deck = session.get(Deck, deck_id)
    if not deck or deck.owner_id != user_id:
        return False
    # Delete review logs for this deck first
    for log in session.exec(select(ReviewLog).where(ReviewLog.deck_id == deck_id)).all():
        session.delete(log)
    # Delete all cards
    for card in session.exec(select(Card).where(Card.deck_id == deck_id)).all():
        session.delete(card)
    session.delete(deck)
    session.commit()
    return True


def get_public_decks(session: Session) -> List[Tuple[Deck, int]]:
    """Returns (Deck, card_count) for every public deck."""
    rows = session.exec(
        select(Deck, func.count(Card.id).label("card_count"))
        .outerjoin(Card, Card.deck_id == Deck.id)
        .where(Deck.public == True)  # noqa: E712
        .group_by(Deck.id)
    ).all()
    return rows


def copy_deck_for_user(session: Session, user_id: UUID, source_deck_id: UUID) -> Optional[Deck]:
    """
    Deep-copy a public deck into a new Deck owned by user_id.
    Every Card is cloned with a fresh SR state.
    Returns the new Deck, or None if the source doesn't exist / isn't public.
    """
    source = session.get(Deck, source_deck_id)
    if not source or not source.public:
        return None

    new_deck = Deck(name=source.name, owner_id=user_id, public=False)
    session.add(new_deck)
    session.flush()  # need new_deck.id before the card loop

    source_cards = session.exec(select(Card).where(Card.deck_id == source_deck_id)).all()
    now = datetime.utcnow()
    for src_card in source_cards:
        clone = Card(
            deck_id=new_deck.id,
            word_id=src_card.word_id,
            state=State.New,
            step=0,
            stability=None,
            difficulty=None,
            due=now,
            last_review=None,
        )
        session.add(clone)

    session.commit()
    session.refresh(new_deck)
    return new_deck


# =========================================================
# CARD
# =========================================================

def get_cards_by_deck(session: Session, deck_id: UUID) -> List[Tuple[Card, Word]]:
    """Returns (Card, Word) pairs for every card in the deck."""
    return session.exec(
        select(Card, Word)
        .join(Word, Card.word_id == Word.id)
        .where(Card.deck_id == deck_id)
    ).all()


def add_card_to_deck(session: Session, deck_id: UUID, word_id: UUID) -> Optional[Tuple[Card, Word]]:
    """Add a word to a deck. Returns None if the word doesn't exist."""
    word = session.get(Word, word_id)
    if not word:
        return None
    card = Card(deck_id=deck_id, word_id=word_id)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card, word


def delete_card(session: Session, user_id: UUID, card_id: UUID) -> bool:
    """Deck owner only. Also removes review logs for this card."""
    card = session.get(Card, card_id)
    if not card:
        return False
    deck = session.get(Deck, card.deck_id)
    if not deck or deck.owner_id != user_id:
        return False
    for log in session.exec(select(ReviewLog).where(ReviewLog.card_id == card_id)).all():
        session.delete(log)
    session.delete(card)
    session.commit()
    return True


def reset_card(session: Session, user_id: UUID, card_id: UUID) -> bool:
    """Reset a card's SR data back to New state (deck owner only)."""
    card = session.get(Card, card_id)
    if not card:
        return False
    deck = session.get(Deck, card.deck_id)
    if not deck or deck.owner_id != user_id:
        return False
    card.state = State.New
    card.step = 0
    card.stability = None
    card.difficulty = None
    card.due = datetime.utcnow()
    card.last_review = None
    session.add(card)
    session.commit()
    return True


# =========================================================
# SRS CORE
# =========================================================

def get_card_by_id(session: Session, card_id: UUID) -> Optional[Tuple[Card, Word]]:
    result = session.exec(
        select(Card, Word).join(Word, Card.word_id == Word.id).where(Card.id == card_id)
    ).first()
    return result


def get_next_card(session: Session, deck_id: UUID) -> Optional[Tuple[Card, Word]]:
    """
    Pick the next card to study from a deck.

    Priority:
      1. Due card with an existing non-New state (earliest due first).
      2. Any New card (earliest created / lowest rowid).

    Returns (Card, Word) or None when nothing is left to study.
    """
    now = datetime.utcnow()

    # 1. Overdue non-new card
    due = session.exec(
        select(Card, Word)
        .join(Word, Card.word_id == Word.id)
        .where(Card.deck_id == deck_id)
        .where(Card.state != State.New)
        .where(Card.due <= now)
        .order_by(Card.due)
        .limit(1)
    ).first()

    if due:
        return due

    # 2. Any new card
    new = session.exec(
        select(Card, Word)
        .join(Word, Card.word_id == Word.id)
        .where(Card.deck_id == deck_id)
        .where(Card.state == State.New)
        .limit(1)
    ).first()

    return new


def update_card_sr(session: Session, card_id: UUID, **updates) -> Optional[Card]:
    card = session.get(Card, card_id)
    if not card:
        return None
    for k, v in updates.items():
        setattr(card, k, v)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def write_review_log(
    session: Session,
    user_id: UUID,
    card_id: UUID,
    deck_id: UUID,
    word_id: UUID,
    state_before: State,
    state_after: State,
    rating: int,
) -> ReviewLog:
    log = ReviewLog(
        user_id=user_id,
        card_id=card_id,
        deck_id=deck_id,
        word_id=word_id,
        state_before=state_before,
        state_after=state_after,
        rating=rating,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


# =========================================================
# PROGRESS STATS — per deck
# =========================================================

def get_deck_progress_stats(session: Session, deck_id: UUID) -> dict:
    now = datetime.utcnow()

    total = session.exec(
        select(func.count(Card.id)).where(Card.deck_id == deck_id)
    ).one() or 0

    state_rows = session.exec(
        select(Card.state, func.count(Card.id))
        .where(Card.deck_id == deck_id)
        .group_by(Card.state)
    ).all()

    stats = {"total": total, "new": 0, "learning": 0, "review": 0, "relearning": 0, "due": 0}
    _map = {State.New: "new", State.Learning: "learning",
            State.Review: "review", State.Relearning: "relearning"}
    for state, count in state_rows:
        key = _map.get(State(state))
        if key:
            stats[key] = count

    due_count = session.exec(
        select(func.count(Card.id))
        .where(Card.deck_id == deck_id)
        .where((Card.state == State.New) | (Card.due <= now))
    ).one() or 0
    stats["due"] = due_count

    return stats


def get_all_deck_stats_for_user(session: Session, user_id: UUID) -> dict:
    """
    Returns { deck_id: { new, learning, review, relearning, due, total } }
    for every deck the user owns.
    """
    now = datetime.utcnow()

    decks = session.exec(select(Deck).where(Deck.owner_id == user_id)).all()
    if not decks:
        return {}

    result = {
        d.id: {"new": 0, "learning": 0, "review": 0, "relearning": 0, "due": 0, "total": 0}
        for d in decks
    }

    # Total cards per deck
    for deck_id, cnt in session.exec(
        select(Card.deck_id, func.count(Card.id))
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .group_by(Card.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["total"] = cnt

    # State counts per deck
    _map = {State.New: "new", State.Learning: "learning",
            State.Review: "review", State.Relearning: "relearning"}
    for deck_id, state, cnt in session.exec(
        select(Card.deck_id, Card.state, func.count(Card.id))
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .group_by(Card.deck_id, Card.state)
    ).all():
        if deck_id in result:
            key = _map.get(State(state))
            if key:
                result[deck_id][key] = cnt

    # Due counts per deck (New cards are always due)
    for deck_id, due_cnt in session.exec(
        select(Card.deck_id, func.count(Card.id))
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .where((Card.state == State.New) | (Card.due <= now))
        .group_by(Card.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["due"] = due_cnt

    return result


# =========================================================
# DAILY REVIEW STATS
# =========================================================

def get_daily_review_stats(session: Session, user_id: UUID, days: int) -> list:
    from datetime import timedelta
    start_date = datetime.utcnow() - timedelta(days=days)

    rows = session.exec(
        select(
            func.date(ReviewLog.reviewed_at).label("date"),
            func.count(ReviewLog.id).label("total"),
            func.sum(case((ReviewLog.state_after == State.Review, 1), else_=0)).label("correct"),
            func.sum(
                case((ReviewLog.state_after.in_([State.Learning, State.Relearning]), 1), else_=0)
            ).label("wrong"),
        )
        .where(ReviewLog.user_id == user_id)
        .where(ReviewLog.reviewed_at >= start_date)
        .group_by(func.date(ReviewLog.reviewed_at))
        .order_by(func.date(ReviewLog.reviewed_at))
    ).all()

    result = []
    for row in rows:
        total = row.total or 0
        correct = row.correct or 0
        wrong = row.wrong or 0
        result.append({
            "date": str(row.date),
            "total": total,
            "correct": correct,
            "wrong": wrong,
            "accuracy": round(correct / total, 4) if total else 0.0,
        })
    return result


# =========================================================
# USER OVERVIEW STATS
# =========================================================

def get_user_overview_stats(session: Session, user_id: UUID) -> dict:
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    deck_ids_q = select(Deck.id).where(Deck.owner_id == user_id)

    total_decks = session.exec(
        select(func.count(Deck.id)).where(Deck.owner_id == user_id)
    ).one() or 0

    total_cards = session.exec(
        select(func.count(Card.id)).where(col(Card.deck_id).in_(deck_ids_q))
    ).one() or 0

    due_cards = session.exec(
        select(func.count(Card.id))
        .where(col(Card.deck_id).in_(deck_ids_q))
        .where((Card.state == State.New) | (Card.due <= now))
    ).one() or 0

    new_cards = session.exec(
        select(func.count(Card.id))
        .where(col(Card.deck_id).in_(deck_ids_q))
        .where(Card.state == State.New)
    ).one() or 0

    reviews_today = session.exec(
        select(func.count(ReviewLog.id))
        .where(ReviewLog.user_id == user_id)
        .where(ReviewLog.reviewed_at >= today_start)
    ).one() or 0

    correct_today = session.exec(
        select(func.count(ReviewLog.id))
        .where(ReviewLog.user_id == user_id)
        .where(ReviewLog.reviewed_at >= today_start)
        .where(ReviewLog.state_after == State.Review)
    ).one() or 0

    accuracy = round(correct_today / reviews_today, 4) if reviews_today else 0.0
    streak_days = _compute_streak(session, user_id, today_start)

    return {
        "total_decks": total_decks,
        "total_cards": total_cards,
        "due_cards": due_cards,
        "new_cards": new_cards,
        "reviews_today": reviews_today,
        "accuracy": accuracy,
        "streak_days": streak_days,
    }


def _compute_streak(session: Session, user_id: UUID, today_start: datetime) -> int:
    streak = 0
    day = today_start
    while True:
        day_end = day + timedelta(days=1)
        count = session.exec(
            select(func.count(ReviewLog.id))
            .where(ReviewLog.user_id == user_id)
            .where(ReviewLog.reviewed_at >= day)
            .where(ReviewLog.reviewed_at < day_end)
        ).one() or 0
        if count == 0:
            break
        streak += 1
        day -= timedelta(days=1)
    return streak

