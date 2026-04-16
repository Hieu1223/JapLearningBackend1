from uuid import UUID
from datetime import datetime
from sqlmodel import Session
from fsrs import Scheduler, Card as FSRSCard, Rating
from ..database.flashcard import queries

class FlashcardController:
    @staticmethod
    def list_decks_with_stats(session: Session, user_id: UUID):
        """Combines deck fetching and stat aggregation for the UI."""
        saved_links = queries.get_user_saved_decks(session, user_id)
        results = []
        for saved_deck, deck_info in saved_links:
            stats_raw = queries.get_deck_inventory_stats(session, saved_deck.id)
            stats = {state.name.lower(): count for state, count in stats_raw}
            
            item = deck_info.model_dump()
            item["user_saved_deck_id"] = saved_deck.id
            item["stats"] = stats
            results.append(item)
        return results

    @staticmethod
    def handle_review(session: Session, sr_data_id: UUID, rating_int: int):
        # Use existing query to get data
        sr_data = queries.get_sr_data_by_id(session, sr_data_id)
        if not sr_data:
            return None

        # FSRS Logic
        scheduler = Scheduler()
        f_card = FSRSCard(
            stability=sr_data.stability or 0.0,
            difficulty=sr_data.difficulty or 0.0,
            reps=sr_data.step or 0,
            state=sr_data.state,
            last_review=sr_data.last_review
        )
        
        info = scheduler.review(f_card, Rating(rating_int), datetime.utcnow())
        new = info.card

        # Use existing query to update
        return queries.update_card_sr(
            session,
            sr_data_id,
            stability=new.stability,
            difficulty=new.difficulty,
            step=new.reps,
            state=new.state,
            due=new.due,
            last_review=datetime.utcnow()
        )
    def add_card_to_deck(
        session, 
        deck_id,
        front ,
        back
    ):
        return queries.add_card_to_deck(
        session, 
        deck_id=deck_id, 
        front=front, 
        back=back
        )