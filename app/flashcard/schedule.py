from fsrs import Scheduler, Card, ReviewLog
from .schema import UserFlashcardSRS, UserSchedulerData


def calculate_next_review(user_flashcard_srs: UserFlashcardSRS, user_scheduler_data: UserSchedulerData, review_result: int):
    card = Card.from_json(user_flashcard_srs.srs_data)
    scheduler = Scheduler.from_json(user_scheduler_data.data)
    card, _ = scheduler.review_card(card, review_result)
    return UserFlashcardSRS(
        id=user_flashcard_srs.id,
        user_flashcard_id=user_flashcard_srs.user_flashcard_id,
        srs_data=card.to_json()
    )

