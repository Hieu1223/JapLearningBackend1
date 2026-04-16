from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal
from ..database.flashcard import State

class DeckResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    public: bool
    cardCount: int # Derived field calculated in controller
    
    model_config = ConfigDict(from_attributes=True)

class CardResponse(BaseModel):
    id: UUID
    deck_id: UUID
    front: str
    back: str
    
    model_config = ConfigDict(from_attributes=True)

class CardSRDataResponse(BaseModel):
    id: UUID
    user_id: UUID
    card_id: UUID
    state: State
    step: Optional[int]
    stability: Optional[float]
    difficulty: Optional[float]
    due: datetime
    last_review: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)

class ReviewRequest(BaseModel):
    card_id: UUID
    user_id: UUID
    rating: Literal["again", "hard", "good", "easy"]

class AddCardRequest(BaseModel):
    word: str
    meaning: str
    deck_id: UUID