from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime, timedelta
import random
import asyncio


router = APIRouter()

# ---- Types ----
SRSRating = Literal["again", "hard", "good", "easy"]

class Flashcard(BaseModel):
    id: str
    front: str
    back: str
    reading: str
    partOfSpeech: str
    deckId: str
    interval: int
    easeFactor: float
    repetitions: int
    nextReview: str
    lastReview: Optional[str] = None

class Deck(BaseModel):
    id: str
    name: str
    cardCount: int


# ---- Mock Data ----
cards: List[Flashcard] = []
decks: List[Deck] = [
    Deck(id="deck-noun", name="Nouns", cardCount=0),
    Deck(id="deck-verb", name="Verbs", cardCount=0),
    Deck(id="deck-adjective", name="Adjectives", cardCount=0),
    Deck(id="deck-particle", name="Particles", cardCount=0),
]


async def delay(ms: int):
    await asyncio.sleep(ms / 1000)


# ---- Endpoints ----

@router.get("/decks", response_model=List[Deck])
async def get_decks():
    await delay(300)
    # update counts dynamically
    for d in decks:
        d.cardCount = sum(1 for c in cards if c.deckId == d.id)
    return [d for d in decks]


@router.get("/cards/due", response_model=List[Flashcard])
async def get_due_cards(deckId: Optional[str] = None):
    await delay(200)
    now = datetime.utcnow()
    return [
        c for c in cards
        if (not deckId or c.deckId == deckId)
        and datetime.fromisoformat(c.nextReview) <= now
    ]


@router.post("/cards/review", response_model=Flashcard)
async def review_card(cardId: str, rating: SRSRating):
    await delay(200)

    card = next((c for c in cards if c.id == cardId), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    interval = card.interval
    easeFactor = card.easeFactor
    repetitions = card.repetitions

    if rating == "again":
        repetitions = 0
        interval = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = round(interval * easeFactor)

        q = 5 if rating == "easy" else 4 if rating == "good" else 3
        easeFactor = max(
            1.3,
            easeFactor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        )

    updated = Flashcard(
        **card.dict(),
        interval=interval,
        easeFactor=easeFactor,
        repetitions=repetitions,
        nextReview=(datetime.utcnow() + timedelta(days=interval)).isoformat(),
        lastReview=datetime.utcnow().isoformat()
    )

    # replace card
    for i, c in enumerate(cards):
        if c.id == cardId:
            cards[i] = updated
            break

    return updated


class AddCardRequest(BaseModel):
    word: str
    meaning: str


@router.post("/cards", response_model=Flashcard)
async def add_card(req: AddCardRequest):
    await delay(500)

    mock_pos = ["noun", "verb", "adjective", "particle"]
    detected_pos = random.choice(mock_pos)

    new_card = Flashcard(
        id=f"card-{int(datetime.utcnow().timestamp() * 1000)}",
        front=req.word,
        back=req.meaning,
        reading=req.word,
        partOfSpeech=detected_pos,
        deckId=f"deck-{detected_pos}",
        interval=1,
        easeFactor=2.5,
        repetitions=0,
        nextReview=datetime.utcnow().isoformat(),
        lastReview=None
    )

    cards.append(new_card)
    return new_card