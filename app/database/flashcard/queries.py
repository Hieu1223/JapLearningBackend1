from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlmodel import Session, select, func, case, col

from .schema import Card, CardSRData, Deck, ReviewLog, UserSavedDeck, State


# =========================================================
# DECK MANAGEMENT
# =========================================================

def add_deck(session: Session, user_id: UUID, name: str, public: bool = False) -> Deck:
    deck = Deck(name=name, owner_id=user_id, public=public)
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return deck


def get_deck_by_id(session: Session, deck_id: UUID) -> Optional[Deck]:
    return session.get(Deck, deck_id)


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
    session.delete(deck)
    session.commit()
    return True


# =========================================================
# PUBLIC DECK BROWSE
# =========================================================

def get_public_decks(session: Session) -> List[Tuple[Deck, int]]:
    statement = (
        select(Deck, func.count(Card.id).label("card_count"))
        .outerjoin(Card, Card.deck_id == Deck.id)
        .where(Deck.public == True)  # noqa: E712
        .group_by(Deck.id)
    )
    return session.exec(statement).all()


# =========================================================
# CARD MANAGEMENT
# front==back — caller passes only `front`; we duplicate it to `back`
# =========================================================

def add_card_to_deck(session: Session, deck_id: UUID, front: str) -> Card:
    card = Card(deck_id=deck_id, front=front, back=front)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def get_cards_by_deck(session: Session, deck_id: UUID) -> List[Card]:
    return session.exec(select(Card).where(Card.deck_id == deck_id)).all()


def update_card(session: Session, user_id: UUID, card_id: UUID, front: str) -> Optional[Card]:
    """Deck owner only. Keeps front == back in sync."""
    card = session.get(Card, card_id)
    if not card:
        return None
    deck = session.get(Deck, card.deck_id)
    if not deck or deck.owner_id != user_id:
        return None
    card.front = front
    card.back = front
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def delete_card(session: Session, user_id: UUID, card_id: UUID) -> bool:
    """Deck owner only. Cascades SR rows for this card across all users."""
    card = session.get(Card, card_id)
    if not card:
        return False
    deck = session.get(Deck, card.deck_id)
    if not deck or deck.owner_id != user_id:
        return False
    for row in session.exec(select(CardSRData).where(CardSRData.card_id == card_id)).all():
        session.delete(row)
    session.delete(card)
    session.commit()
    return True


def get_sr_data_for_card(session: Session, card_id: UUID) -> List[CardSRData]:
    """All SR rows across every user for a given card (used after card content update)."""
    return session.exec(select(CardSRData).where(CardSRData.card_id == card_id)).all()


# =========================================================
# USER SAVED DECK
# =========================================================

def get_user_saved_decks(session: Session, user_id: UUID) -> List[Tuple[UserSavedDeck, Deck]]:
    return session.exec(
        select(UserSavedDeck, Deck)
        .join(Deck, UserSavedDeck.deck_id == Deck.id)
        .where(UserSavedDeck.user_id == user_id)
    ).all()


def save_deck_for_user(
    session: Session, user_id: UUID, deck_id: UUID
) -> Optional[UserSavedDeck]:
    """
    Create the UserSavedDeck record only.
    SR rows are created lazily the first time each card is served.
    """
    if not session.get(Deck, deck_id):
        return None
    saved = UserSavedDeck(user_id=user_id, deck_id=deck_id)
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return saved


def delete_saved_deck(session: Session, user_id: UUID, user_saved_deck_id: UUID) -> bool:
    """Remove saved deck and its SR rows; source Deck/Card untouched."""
    saved = session.get(UserSavedDeck, user_saved_deck_id)
    if not saved or saved.user_id != user_id:
        return False
    for row in session.exec(
        select(CardSRData).where(CardSRData.user_saved_deck_id == user_saved_deck_id)
    ).all():
        session.delete(row)
    session.delete(saved)
    session.commit()
    return True


def delete_learned_card(
    session: Session, user_id: UUID, user_saved_deck_id: UUID, card_id: UUID
) -> bool:
    """
    Remove one card's SR row from a user's saved deck so it reverts to
    unseen — the next fetch will lazy-create a fresh State.New row.
    """
    saved = session.get(UserSavedDeck, user_saved_deck_id)
    if not saved or saved.user_id != user_id:
        return False
    sr = session.exec(
        select(CardSRData)
        .where(CardSRData.user_saved_deck_id == user_saved_deck_id)
        .where(CardSRData.card_id == card_id)
    ).first()
    if not sr:
        return False
    session.delete(sr)
    session.commit()
    return True


# =========================================================
# SRS CORE
# =========================================================

def get_sr_data_by_id(session: Session, sr_data_id: UUID) -> Optional[CardSRData]:
    return session.get(CardSRData, sr_data_id)


def get_next_card(
    session: Session, user_saved_deck_id: UUID
) -> Optional[Tuple[Card, CardSRData]]:
    """
    Pick the next card to study.

    Priority:
      1. Existing SR row that is due now (earliest due first).
      2. Any card in the deck with no SR row yet (lazy-create on pick).

    Always returns (Card, CardSRData) or None.
    """
    saved = session.get(UserSavedDeck, user_saved_deck_id)
    if not saved:
        return None

    now = datetime.utcnow()

    # 1. Due card with an existing SR row
    due_result = session.exec(
        select(Card, CardSRData)
        .join(CardSRData, Card.id == CardSRData.card_id)
        .where(CardSRData.user_saved_deck_id == user_saved_deck_id)
        .where(CardSRData.due <= now)
        .order_by(CardSRData.due)
        .limit(1)
    ).first()

    if due_result:
        return due_result

    # 2. Unseen card — no SR row exists yet
    seen_card_ids = select(CardSRData.card_id).where(
        CardSRData.user_saved_deck_id == user_saved_deck_id
    )
    new_card = session.exec(
        select(Card)
        .where(Card.deck_id == saved.deck_id)
        .where(~col(Card.id).in_(seen_card_ids))
        .limit(1)
    ).first()

    if not new_card:
        return None

    # Lazily create the SR row now that the card is about to be shown
    sr = CardSRData(
        user_saved_deck_id=user_saved_deck_id,
        card_id=new_card.id,
        state=State.New,
        due=now,
    )
    session.add(sr)
    session.commit()
    session.refresh(sr)
    return new_card, sr


def update_card_sr(session: Session, sr_data_id: UUID, **updates) -> Optional[CardSRData]:
    sr = session.get(CardSRData, sr_data_id)
    if not sr:
        return None
    for k, v in updates.items():
        setattr(sr, k, v)
    session.add(sr)
    session.commit()
    session.refresh(sr)
    return sr


def write_review_log(
    session: Session,
    user_id: UUID,
    card_id: UUID,
    user_saved_deck_id: UUID,
    state_before: State,
    state_after: State,
    rating: int,
) -> ReviewLog:
    log = ReviewLog(
        user_id=user_id,
        card_id=card_id,
        user_saved_deck_id=user_saved_deck_id,
        state_before=state_before,
        state_after=state_after,
        rating=rating,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


# =========================================================
# PROGRESS STATS — per (user, deck)
#
# With lazy init the counts must be:
#   total       = all cards in the source deck
#   new         = unseen cards (no SR row)  +  SR rows with state=New
#   learning    = SR rows with state=Learning
#   review      = SR rows with state=Review
#   relearning  = SR rows with state=Relearning
#   due         = overdue SR rows  +  unseen cards (always due)
# =========================================================

def get_deck_progress_stats(
    session: Session, user_id: UUID, deck_id: UUID
) -> dict:
    saved = session.exec(
        select(UserSavedDeck)
        .where(UserSavedDeck.user_id == user_id)
        .where(UserSavedDeck.deck_id == deck_id)
    ).first()

    stats = {"total": 0, "new": 0, "learning": 0, "review": 0, "relearning": 0, "due": 0}
    if not saved:
        return stats

    now = datetime.utcnow()

    total = session.exec(
        select(func.count(Card.id)).where(Card.deck_id == deck_id)
    ).one() or 0
    stats["total"] = total

    _name_map = {
        State.New: "new",
        State.Learning: "learning",
        State.Review: "review",
        State.Relearning: "relearning",
    }
    sr_rows = session.exec(
        select(CardSRData.state, func.count(CardSRData.id))
        .where(CardSRData.user_saved_deck_id == saved.id)
        .group_by(CardSRData.state)
    ).all()

    seen_count = 0
    for state, count in sr_rows:
        key = _name_map.get(State(state))
        if key:
            stats[key] = count
        seen_count += count

    unseen = total - seen_count
    stats["new"] += unseen  # unseen cards are implicitly new

    due_sr = session.exec(
        select(func.count(CardSRData.id))
        .where(CardSRData.user_saved_deck_id == saved.id)
        .where(CardSRData.due <= now)
    ).one() or 0
    stats["due"] = due_sr + unseen  # unseen cards are always due

    return stats


# =========================================================
# DECK-LEVEL STATS — for the deck list (all saved decks in one pass)
# =========================================================

def get_all_deck_stats_for_user(session: Session, user_id: UUID) -> dict:
    """
    Returns { deck_id: { new, learning, review, relearning, due, total } }
    for every deck the user has saved. Unseen cards count as new + due.
    """
    now = datetime.utcnow()

    saved_rows = session.exec(
        select(UserSavedDeck).where(UserSavedDeck.user_id == user_id)
    ).all()
    if not saved_rows:
        return {}

    # Build lookup tables
    result: dict[UUID, dict] = {}
    deck_to_saved: dict[UUID, UUID] = {}
    for saved in saved_rows:
        result[saved.deck_id] = {
            "new": 0, "learning": 0, "review": 0, "relearning": 0,
            "due": 0, "total": 0, "_seen": 0,
        }
        deck_to_saved[saved.deck_id] = saved.id

    # Total cards per deck
    for deck_id, cnt in session.exec(
        select(UserSavedDeck.deck_id, func.count(Card.id).label("cnt"))
        .join(Card, Card.deck_id == UserSavedDeck.deck_id)
        .where(UserSavedDeck.user_id == user_id)
        .group_by(UserSavedDeck.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["total"] = cnt

    # SR state counts
    _name_map = {
        State.New: "new",
        State.Learning: "learning",
        State.Review: "review",
        State.Relearning: "relearning",
    }
    for deck_id, state, cnt in session.exec(
        select(
            UserSavedDeck.deck_id,
            CardSRData.state,
            func.count(CardSRData.id).label("cnt"),
        )
        .join(CardSRData, CardSRData.user_saved_deck_id == UserSavedDeck.id)
        .where(UserSavedDeck.user_id == user_id)
        .group_by(UserSavedDeck.deck_id, CardSRData.state)
    ).all():
        if deck_id not in result:
            continue
        key = _name_map.get(State(state))
        if key:
            result[deck_id][key] = cnt
        result[deck_id]["_seen"] += cnt

    # Due SR rows per deck
    for deck_id, due_cnt in session.exec(
        select(UserSavedDeck.deck_id, func.count(CardSRData.id).label("due_cnt"))
        .join(CardSRData, CardSRData.user_saved_deck_id == UserSavedDeck.id)
        .where(UserSavedDeck.user_id == user_id)
        .where(CardSRData.due <= now)
        .group_by(UserSavedDeck.deck_id)
    ).all():
        if deck_id in result:
            result[deck_id]["due"] = due_cnt

    # Fold unseen into new + due, remove scratch field
    for data in result.values():
        unseen = data["total"] - data["_seen"]
        if unseen > 0:
            data["new"] += unseen
            data["due"] += unseen
        del data["_seen"]

    return result


# =========================================================
# DAILY REVIEW STATS  (sourced from ReviewLog)
#
# correct = reviews that ended in state=Review  (card is mastered / staying)
# wrong   = reviews that ended in Learning or Relearning  (lapses / still learning)
# =========================================================

def get_daily_review_stats(session: Session, user_id: UUID, days: int) -> List[dict]:
    start_date = datetime.utcnow() - timedelta(days=days)

    rows = session.exec(
        select(
            func.date(ReviewLog.reviewed_at).label("date"),
            func.count(ReviewLog.id).label("total"),
            func.sum(
                case((ReviewLog.state_after == State.Review, 1), else_=0)
            ).label("correct"),
            func.sum(
                case(
                    (ReviewLog.state_after.in_([State.Learning, State.Relearning]), 1),
                    else_=0,
                )
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

    total_decks = session.exec(
        select(func.count(UserSavedDeck.id)).where(UserSavedDeck.user_id == user_id)
    ).one() or 0

    # Total cards across all source decks the user has saved
    total_cards = session.exec(
        select(func.count(Card.id))
        .join(UserSavedDeck, UserSavedDeck.deck_id == Card.deck_id)
        .where(UserSavedDeck.user_id == user_id)
    ).one() or 0

    # Cards with an SR row (seen at least once)
    seen_cards = session.exec(
        select(func.count(CardSRData.id))
        .join(UserSavedDeck, CardSRData.user_saved_deck_id == UserSavedDeck.id)
        .where(UserSavedDeck.user_id == user_id)
    ).one() or 0

    unseen_cards = max(0, total_cards - seen_cards)

    # Due: overdue SR rows + all unseen (unseen are always due)
    due_sr = session.exec(
        select(func.count(CardSRData.id))
        .join(UserSavedDeck, CardSRData.user_saved_deck_id == UserSavedDeck.id)
        .where(UserSavedDeck.user_id == user_id)
        .where(CardSRData.due <= now)
    ).one() or 0
    due_cards = due_sr + unseen_cards

    # New: SR rows in state New + unseen
    new_sr = session.exec(
        select(func.count(CardSRData.id))
        .join(UserSavedDeck, CardSRData.user_saved_deck_id == UserSavedDeck.id)
        .where(UserSavedDeck.user_id == user_id)
        .where(CardSRData.state == State.New)
    ).one() or 0
    new_cards = new_sr + unseen_cards

    # Today stats from ReviewLog (accurate, immutable)
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
    """
    Count consecutive days ending today (inclusive) where the user
    completed at least one review, walking back through ReviewLog.
    """
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