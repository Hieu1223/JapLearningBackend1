"""
database/flashcard/queries.py
"""

from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List

from sqlmodel import Session, select, func, case, col

from .schema import Card, Deck, ReviewLog, State


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
    for log in session.exec(select(ReviewLog).where(ReviewLog.deck_id == deck_id)).all():
        session.delete(log)
    for card in session.exec(select(Card).where(Card.deck_id == deck_id)).all():
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
    now = datetime.utcnow()
    for src_card in source_cards:
        clone = Card(
            deck_id=new_deck.id,
            word_id=src_card.word_id,
            front=src_card.front,
            back=src_card.back,
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


def get_cards_by_deck(session: Session, deck_id: UUID) -> List[Card]:
    return session.exec(
        select(Card).where(Card.deck_id == deck_id)
    ).all()


def add_card_to_deck(session: Session, deck_id: UUID, front: str, back: str) -> Card:
    card = Card(deck_id=deck_id, front=front, back=back)
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
    for log in session.exec(select(ReviewLog).where(ReviewLog.card_id == card_id)).all():
        session.delete(log)
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
    card.state = State.New
    card.step = 0
    card.stability = None
    card.difficulty = None
    card.due = datetime.utcnow()
    card.last_review = None
    session.add(card)
    session.commit()
    return True


def get_card_by_id(session: Session, card_id: UUID) -> Optional[Card]:
    return session.get(Card, card_id)


def get_next_card(session: Session, deck_id: UUID) -> Optional[Card]:
    now = datetime.utcnow()

    due = session.exec(
        select(Card)
        .where(Card.deck_id == deck_id)
        .where(Card.state != State.New)
        .where(Card.due <= now)
        .order_by(Card.due)
        .limit(1)
    ).first()

    if due:
        return due

    new = session.exec(
        select(Card)
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
    word_id: Optional[UUID],
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
    now = datetime.utcnow()

    decks = session.exec(select(Deck).where(Deck.owner_id == user_id)).all()
    if not decks:
        return {}

    result = {
        d.id: {"new": 0, "learning": 0, "review": 0, "relearning": 0, "due": 0, "total": 0}
        for d in decks
    }

    for deck_id, cnt in session.exec(
        select(Card.deck_id, func.count(Card.id))
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .group_by(Card.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["total"] = cnt

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

    for deck_id, due_cnt in session.exec(
        select(Card.deck_id, func.count(Card.id))
        .where(col(Card.deck_id).in_([d.id for d in decks]))
        .where((Card.state == State.New) | (Card.due <= now))
        .group_by(Card.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["due"] = due_cnt

    return result


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

