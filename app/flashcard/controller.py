from uuid import UUID
from typing import Optional, List
from datetime import datetime, timedelta

from sqlmodel import Session

from ..database.flashcard import queries as q
from ..database.flashcard.schema import Card, State
from .schema import (
    CardResponse,
    CardSRDataResponse,
    DeckProgressResponse,
    DeckStatsResponse,
    DeckWithStatsResponse,
    DailyStatResponse,
    OverviewStatsResponse,
    PublicDeckResponse,
    db_state_to_card_state,
)


# =========================================================
# INTERNAL HELPERS
# =========================================================

def _sr_to_response(sr, card) -> CardSRDataResponse:
    return CardSRDataResponse(
        sr_data_id=sr.id,
        card_id=sr.card_id,
        user_saved_deck_id=sr.user_saved_deck_id,
        front=card.front,
        state=db_state_to_card_state(State(sr.state)),
        step=sr.step,
        stability=sr.stability,
        difficulty=sr.difficulty,
        due=sr.due,
        last_review=sr.last_review,
    )


# =========================================================
# FSRS-STYLE SRS ALGORITHM
# =========================================================

def _apply_srs(sr, rating: int):
    """
    rating: 1=Again  2=Hard  3=Good  4=Easy
    Mutates sr in-place, returns it.
    """
    now = datetime.utcnow()
    sr.last_review = now

    if sr.state == State.New:
        sr.state = State.Learning
        sr.step = 0

    if sr.state in (State.Learning, State.Relearning):
        if rating == 1:       # Again
            sr.step = 0
            sr.due = now + timedelta(minutes=1)
        elif rating == 2:     # Hard
            sr.due = now + timedelta(minutes=5)
        elif rating == 3:     # Good
            sr.step = (sr.step or 0) + 1
            if sr.step >= 2:
                sr.state = State.Review
                sr.stability = sr.stability or 1.0
                sr.difficulty = sr.difficulty or 5.0
                sr.due = now + timedelta(days=max(1, int(sr.stability)))
            else:
                sr.due = now + timedelta(minutes=10)
        else:                 # Easy
            sr.state = State.Review
            sr.stability = (sr.stability or 1.0) * 2
            sr.difficulty = max(1.0, (sr.difficulty or 5.0) - 0.5)
            sr.due = now + timedelta(days=max(1, int(sr.stability)))

    elif sr.state == State.Review:
        if rating == 1:       # Again — lapse
            sr.state = State.Relearning
            sr.step = 0
            sr.stability = max(1.0, (sr.stability or 1.0) * 0.5)
            sr.due = now + timedelta(minutes=10)
        else:
            multiplier = {2: 1.2, 3: 2.5, 4: 3.5}.get(rating, 2.5)
            sr.stability = max(1.0, (sr.stability or 1.0) * multiplier)
            if rating >= 3:
                sr.difficulty = max(1.0, (sr.difficulty or 5.0) - 0.1)
            sr.due = now + timedelta(days=int(sr.stability))

    return sr


# =========================================================
# FLASHCARD CONTROLLER
# =========================================================

class FlashcardController:

    # ----- Decks -----

    @staticmethod
    def create_deck(session: Session, user_id: UUID, name: str, public: bool = False):
        return q.add_deck(session, user_id, name, public)

    @staticmethod
    def update_deck(session: Session, user_id: UUID, deck_id: UUID, name: Optional[str]):
        if name is None:
            return session.get(q.Deck, deck_id)
        return q.update_deck(session, user_id, deck_id, name)

    @staticmethod
    def delete_deck(session: Session, user_id: UUID, deck_id: UUID) -> bool:
        return q.delete_deck(session, user_id, deck_id)

    @staticmethod
    def list_decks_with_stats(session: Session, user_id: UUID) -> List[DeckWithStatsResponse]:
        saved_decks = q.get_user_saved_decks(session, user_id)      # [(UserSavedDeck, Deck)]
        all_stats = q.get_all_deck_stats_for_user(session, user_id) # {deck_id: stats_dict}

        result = []
        for saved, deck in saved_decks:
            raw = all_stats.get(deck.id, {})
            stats = DeckStatsResponse(
                new=raw.get("new", 0),
                learning=raw.get("learning", 0),
                review=raw.get("review", 0),
                relearning=raw.get("relearning", 0),
                due=raw.get("due", 0),
            )
            result.append(DeckWithStatsResponse(
                id=deck.id,
                name=deck.name,
                owner_id=deck.owner_id,
                public=deck.public,
                user_saved_deck_id=saved.id,
                stats=stats,
            ))
        return result

    @staticmethod
    def get_public_decks(session: Session) -> List[PublicDeckResponse]:
        return [
            PublicDeckResponse(id=deck.id, name=deck.name, owner_id=deck.owner_id, card_count=cnt)
            for deck, cnt in q.get_public_decks(session)
        ]

    # ----- Saved Decks -----

    @staticmethod
    def save_deck_for_user(session: Session, user_id: UUID, deck_id: UUID):
        return q.save_deck_for_user(session, user_id, deck_id)

    @staticmethod
    def delete_saved_deck(session: Session, user_id: UUID, user_saved_deck_id: UUID) -> bool:
        return q.delete_saved_deck(session, user_id, user_saved_deck_id)

    # ----- Cards -----

    @staticmethod
    def list_cards(session: Session, deck_id: UUID) -> List[CardResponse]:
        return q.get_cards_by_deck(session, deck_id)

    @staticmethod
    def add_card_to_deck(session: Session, deck_id: UUID, front: str) -> CardResponse:
        return q.add_card_to_deck(session, deck_id, front)

    @staticmethod
    def update_card(
        session: Session, user_id: UUID, card_id: UUID, front: str
    ) -> Optional[CardResponse]:
        """
        Update the card's front (and back, since they're always equal).
        Returns just the updated CardResponse — SR data is unchanged by a
        content edit; the client already has the SR record and only the
        display text has changed.
        """
        return q.update_card(session, user_id, card_id, front)

    @staticmethod
    def delete_card(session: Session, user_id: UUID, card_id: UUID) -> bool:
        return q.delete_card(session, user_id, card_id)

    @staticmethod
    def delete_learned_card(
        session: Session, user_id: UUID, user_saved_deck_id: UUID, card_id: UUID
    ) -> bool:
        return q.delete_learned_card(session, user_id, user_saved_deck_id, card_id)

    # ----- SRS -----

    @staticmethod
    def fetch_due_card(
        session: Session, user_saved_deck_id: UUID
    ) -> Optional[CardSRDataResponse]:
        result = q.get_next_card(session, user_saved_deck_id)
        if not result:
            return None
        card, sr = result
        return _sr_to_response(sr, card)

    @staticmethod
    def handle_review(
        session: Session,
        user_id: UUID,
        sr_data_id: UUID,
        rating: int,
    ) -> Optional[CardSRDataResponse]:
        sr = q.get_sr_data_by_id(session, sr_data_id)
        if not sr:
            return None

        card = session.get(Card, sr.card_id)
        if not card:
            return None

        state_before = State(sr.state)
        _apply_srs(sr, rating)
        state_after = State(sr.state)

        updated = q.update_card_sr(
            session, sr_data_id,
            state=sr.state,
            step=sr.step,
            stability=sr.stability,
            difficulty=sr.difficulty,
            due=sr.due,
            last_review=sr.last_review,
        )
        if not updated:
            return None

        # Write immutable log entry for stats / streaks
        q.write_review_log(
            session,
            user_id=user_id,
            card_id=sr.card_id,
            user_saved_deck_id=sr.user_saved_deck_id,
            state_before=state_before,
            state_after=state_after,
            rating=rating,
        )

        return _sr_to_response(updated, card)

    # ----- Progress & Stats -----

    @staticmethod
    def get_deck_progress(
        session: Session, user_id: UUID, deck_id: UUID
    ) -> DeckProgressResponse:
        return DeckProgressResponse(**q.get_deck_progress_stats(session, user_id, deck_id))

    @staticmethod
    def get_daily_stats(
        session: Session, user_id: UUID, days: int
    ) -> List[DailyStatResponse]:
        return [DailyStatResponse(**row) for row in q.get_daily_review_stats(session, user_id, days)]

    @staticmethod
    def get_overview_stats(session: Session, user_id: UUID) -> OverviewStatsResponse:
        return OverviewStatsResponse(**q.get_user_overview_stats(session, user_id))