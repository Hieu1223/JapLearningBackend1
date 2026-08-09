from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any
import json

from sqlmodel import Session

from ..database.flashcard import queries as q
from ..database.flashcard.schema import Card, CardType, make_sorting_id
from .schema import (
    CardResponse,
    CardWithSrsResponse,
    CardState,
    DeckProgressResponse,
    DeckStatsResponse,
    DeckWithStatsResponse,
    DeckResponse,
    PublicDeckResponse,
    ReviewSessionResponse,
    ReviewSessionWithSrsResponse,
)

# ts-fsrs State enum values
FSRS_STATE = {"New": 0, "Learning": 1, "Review": 2, "Relearning": 3}
STATE_TO_FSRS = {0: "New", 1: "Learning", 2: "Review", 3: "Relearning"}


def _parse_iso(value) -> Optional[datetime]:
    """Parse a ts-fsrs date (ISO string, epoch-ms int, or null) to datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        # ts-fsrs afterHandler often emits epoch ms
        return datetime.fromtimestamp(value / 1000)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _state_to_int(state) -> int:
    if isinstance(state, int):
        return state
    return FSRS_STATE.get(str(state), 0)


def _fsrs_card_to_srs_fields(card: dict) -> dict:
    """Map a ts-fsrs Card JSON object to SrsCard column values."""
    return {
        "due": _parse_iso(card.get("due")) or datetime.utcnow(),
        "stability": float(card.get("stability") or 0.0),
        "difficulty": float(card.get("difficulty") or 0.0),
        "elapsed_days": int(card.get("elapsed_days") or 0),
        "scheduled_days": int(card.get("scheduled_days") or 0),
        "learning_steps": int(card.get("learning_steps") or 0),
        "reps": int(card.get("reps") or 0),
        "lapses": int(card.get("lapses") or 0),
        "state": _state_to_int(card.get("state")),
        "last_review": _parse_iso(card.get("last_review")),
    }


def _srs_to_fsrs_card(srs) -> dict:
    """Serialize an SrsCard row back into a ts-fsrs Card object."""
    return {
        "due": srs.due.isoformat() if srs.due else None,
        "stability": srs.stability,
        "difficulty": srs.difficulty,
        "elapsed_days": srs.elapsed_days,
        "scheduled_days": srs.scheduled_days,
        "learning_steps": srs.learning_steps,
        "reps": srs.reps,
        "lapses": srs.lapses,
        "state": STATE_TO_FSRS.get(srs.state, "New"),
        "last_review": srs.last_review.isoformat() if srs.last_review else None,
    }


def _card_to_response(card: Card, srs=None) -> CardResponse:
    if srs is None:
        state = CardState.NEW
        due = None
        last_review = None
        step = None
        stability = None
        difficulty = None
    else:
        state = CardState(STATE_TO_FSRS.get(srs.state, "New").lower())
        # New cards have no meaningful due date yet.
        due = srs.due if srs.state != 0 else None
        last_review = srs.last_review
        step = srs.learning_steps or None
        stability = srs.stability or None
        difficulty = srs.difficulty or None

    return CardResponse(
        id=card.id,
        deck_id=card.deck_id,
        data=card.data,
        card_type=card.card_type,
        state=state,
        step=step,
        stability=stability,
        difficulty=difficulty,
        due=due,
        last_review=last_review,
    )


def _card_with_srs_to_response(card: Card, srs: Any) -> CardWithSrsResponse:
    fsrs_card = _srs_to_fsrs_card(srs)
    return CardWithSrsResponse(
        id=card.id,
        deck_id=card.deck_id,
        data=card.data,
        card_type=card.card_type,
        srs_queue=srs.state,
        srs_due=int(srs.due.timestamp() * 1000) if srs.due else None,
        srs_factor=None,
        srs_left=fsrs_card["learning_steps"],
        srs_ivl=fsrs_card["scheduled_days"],
        srs_reps=fsrs_card["reps"],
        srs_lapses=fsrs_card["lapses"],
        srs_data=json.dumps(fsrs_card),
    )


class FlashcardService:

    def create_deck(self, session: Session, user_id: UUID, name: str, public: bool = False) -> DeckWithStatsResponse:
        deck = q.add_deck(session, user_id, name, public)
        return DeckWithStatsResponse(
            id=deck.id, name=deck.name, owner_id=deck.owner_id, public=deck.public,
            stats=DeckStatsResponse(),
        )

    def update_deck(self, session: Session, user_id: UUID, deck_id: UUID, name: str) -> Optional[DeckResponse]:
        deck = q.update_deck(session, user_id, deck_id, name)
        return deck

    def delete_deck(self, session: Session, user_id: UUID, deck_id: UUID) -> bool:
        return q.delete_deck(session, user_id, deck_id)

    def list_decks_with_stats(self, session: Session, user_id: UUID) -> List[DeckWithStatsResponse]:
        decks = q.get_decks_for_user(session, user_id)
        all_stats = q.get_all_deck_srs_stats_for_user(session, user_id)

        result = []
        for deck in decks:
            raw = all_stats.get(deck.id, {})
            stats = DeckStatsResponse(
                new=raw.get("new", 0),
                learning=raw.get("learning", 0),
                due=raw.get("due", 0),
            )
            result.append(DeckWithStatsResponse(
                id=deck.id, name=deck.name, owner_id=deck.owner_id,
                public=deck.public, stats=stats,
            ))
        return result

    def get_public_decks(self, session: Session) -> List[PublicDeckResponse]:
        return [
            PublicDeckResponse(id=deck.id, name=deck.name, owner_id=deck.owner_id, card_count=cnt)
            for deck, cnt in q.get_public_decks(session)
        ]

    def copy_deck(self, session: Session, user_id: UUID, source_deck_id: UUID) -> Optional[DeckWithStatsResponse]:
        deck = q.copy_deck_for_user(session, user_id, source_deck_id)
        if not deck:
            return None
        return DeckWithStatsResponse(
            id=deck.id, name=deck.name, owner_id=deck.owner_id, public=deck.public,
            stats=DeckStatsResponse(new=q.get_deck_srs_stats(session, deck.id)["new"]),
        )

    def list_cards(self, session: Session, deck_id: UUID) -> List[CardResponse]:
        cards = q.get_cards_by_deck(session, deck_id)
        result = []
        for card in cards:
            srs = q.get_srs_card(session, card.id)
            result.append(_card_to_response(card, srs))
        return result

    def add_vocab(
        self,
        session: Session,
        user_id: UUID,
        deck_id: UUID,
        word: str,
        meaning: str,
    ) -> Optional[CardResponse]:
        deck = q.get_deck_by_id(session, deck_id)
        if not deck or deck.owner_id != user_id:
            return None

        data = json.dumps({"word": word, "meaning": meaning})
        sorting_id = make_sorting_id(CardType.VOCAB, word=word)
        card = q.add_card_to_deck(session, deck_id, data, CardType.VOCAB, sorting_id)
        q.create_srs_card(session, card.id, deck_id)
        srs = q.get_srs_card(session, card.id)
        return _card_to_response(card, srs)

    def delete_card(self, session: Session, user_id: UUID, card_id: UUID) -> bool:
        return q.delete_card(session, user_id, card_id)

    def reset_card(self, session: Session, user_id: UUID, card_id: UUID) -> bool:
        return q.reset_card(session, user_id, card_id)

    def load_review_session(
        self, session: Session, deck_id: UUID, limit: int = 20
    ) -> List[CardResponse]:
        cards = q.get_due_cards(session, deck_id, limit)
        result = []
        for card in cards:
            srs = q.get_srs_card(session, card.id)
            result.append(_card_to_response(card, srs))
        return result

    def load_review_session_with_srs(
        self, session: Session, deck_id: UUID, limit: int = 20
    ) -> ReviewSessionWithSrsResponse:
        cards = q.get_due_cards(session, deck_id, limit)
        result = []
        for card in cards:
            srs = q.get_srs_card(session, card.id)
            if srs:
                result.append(_card_with_srs_to_response(card, srs))
        return ReviewSessionWithSrsResponse(cards=result, total=len(result))

    def save_review(
        self,
        session: Session,
        user_id: UUID,
        card_id: UUID,
        card: dict,
    ) -> Optional[CardResponse]:
        """Persist a ts-fsrs Card object computed by the frontend scheduler.

        ``card`` is the fsrs ``Card`` JSON (dates as ISO strings or epoch ms).
        """
        db_card = q.get_card_by_id(session, card_id)
        if not db_card:
            return None

        deck = q.get_deck_by_id(session, db_card.deck_id)
        if not deck or deck.owner_id != user_id:
            return None

        srs = q.get_srs_card(session, card_id)
        if not srs:
            return None

        fields = _fsrs_card_to_srs_fields(card)
        srs = q.update_srs_card(session, srs, **fields)

        return _card_to_response(db_card, srs)

    def get_deck_progress(self, session: Session, deck_id: UUID) -> DeckProgressResponse:
        return DeckProgressResponse(**q.get_deck_srs_stats(session, deck_id))