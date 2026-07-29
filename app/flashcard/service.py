from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List

from sqlmodel import Session

from ..database.flashcard import queries as q
from ..database.flashcard.schema import Card, State
from .schema import (
    CardResponse,
    CardState,
    DeckProgressResponse,
    DeckStatsResponse,
    DeckWithStatsResponse,
    DeckResponse,
    DailyStatResponse,
    OverviewStatsResponse,
    PublicDeckResponse,
    db_state_to_card_state,
)


def _card_to_response(card: Card) -> CardResponse:
    return CardResponse(
        id=card.id,
        deck_id=card.deck_id,
        front=card.front,
        back=card.back,
        state=db_state_to_card_state(State(card.state)),
        step=card.step,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due,
        last_review=card.last_review,
    )


def _apply_srs(card: Card, rating: int) -> Card:
    now = datetime.utcnow()
    card.last_review = now

    if card.state == State.New:
        card.state = State.Learning
        card.step = 0

    if card.state in (State.Learning, State.Relearning):
        if rating == 1:
            card.step = 0
            card.due = now + timedelta(minutes=1)
        elif rating == 2:
            card.due = now + timedelta(minutes=5)
        elif rating == 3:
            card.step = (card.step or 0) + 1
            if card.step >= 2:
                card.state = State.Review
                card.stability = card.stability or 1.0
                card.difficulty = card.difficulty or 5.0
                card.due = now + timedelta(days=max(1, int(card.stability)))
            else:
                card.due = now + timedelta(minutes=10)
        else:
            card.state = State.Review
            card.stability = (card.stability or 1.0) * 2
            card.difficulty = max(1.0, (card.difficulty or 5.0) - 0.5)
            card.due = now + timedelta(days=max(1, int(card.stability)))

    elif card.state == State.Review:
        if rating == 1:
            card.state = State.Relearning
            card.step = 0
            card.stability = max(1.0, (card.stability or 1.0) * 0.5)
            card.due = now + timedelta(minutes=10)
        else:
            multiplier = {2: 1.2, 3: 2.5, 4: 3.5}.get(rating, 2.5)
            card.stability = max(1.0, (card.stability or 1.0) * multiplier)
            if rating >= 3:
                card.difficulty = max(1.0, (card.difficulty or 5.0) - 0.1)
            card.due = now + timedelta(days=int(card.stability))

    return card


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
        all_stats = q.get_all_deck_stats_for_user(session, user_id)

        result = []
        for deck in decks:
            raw = all_stats.get(deck.id, {})
            stats = DeckStatsResponse(
                new=raw.get("new", 0),
                learning=raw.get("learning", 0),
                review=raw.get("review", 0),
                relearning=raw.get("relearning", 0),
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
            stats=DeckStatsResponse(new=q.get_deck_progress_stats(session, deck.id)["new"]),
        )

    def list_cards(self, session: Session, deck_id: UUID) -> List[CardResponse]:
        return [_card_to_response(card) for card in q.get_cards_by_deck(session, deck_id)]

    def add_card(
        self,
        session: Session,
        user_id: UUID,
        deck_id: UUID,
        front: str,
        back: str,
    ) -> Optional[CardResponse]:
        deck = q.get_deck_by_id(session, deck_id)
        if not deck or deck.owner_id != user_id:
            return None
        card = q.add_card_to_deck(session, deck_id, front=front, back=back)
        return _card_to_response(card)

    def delete_card(self, session: Session, user_id: UUID, card_id: UUID) -> bool:
        return q.delete_card(session, user_id, card_id)

    def reset_card(self, session: Session, user_id: UUID, card_id: UUID) -> bool:
        return q.reset_card(session, user_id, card_id)

    def fetch_due_card(self, session: Session, deck_id: UUID) -> Optional[CardResponse]:
        card = q.get_next_card(session, deck_id)
        if not card:
            return None
        return _card_to_response(card)

    def handle_review(
        self,
        session: Session,
        user_id: UUID,
        card_id: UUID,
        rating: int,
    ) -> Optional[CardResponse]:
        card = q.get_card_by_id(session, card_id)
        if not card:
            return None

        deck = q.get_deck_by_id(session, card.deck_id)
        if not deck or deck.owner_id != user_id:
            return None

        state_before = State(card.state)
        _apply_srs(card, rating)
        state_after = State(card.state)

        updated = q.update_card_sr(
            session, card_id,
            state=card.state,
            step=card.step,
            stability=card.stability,
            difficulty=card.difficulty,
            due=card.due,
            last_review=card.last_review,
        )
        if not updated:
            return None

        q.write_review_log(
            session,
            user_id=user_id,
            card_id=card_id,
            deck_id=card.deck_id,
            word_id=card.word_id,
            state_before=state_before,
            state_after=state_after,
            rating=rating,
        )

        return _card_to_response(updated)

    def get_deck_progress(self, session: Session, deck_id: UUID) -> DeckProgressResponse:
        return DeckProgressResponse(**q.get_deck_progress_stats(session, deck_id))

    def get_daily_stats(self, session: Session, user_id: UUID, days: int) -> List[DailyStatResponse]:
        return [DailyStatResponse(**row) for row in q.get_daily_review_stats(session, user_id, days)]

    def get_overview_stats(self, session: Session, user_id: UUID) -> OverviewStatsResponse:
        return OverviewStatsResponse(**q.get_user_overview_stats(session, user_id))