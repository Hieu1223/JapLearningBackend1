from pydantic import BaseModel
from uuid import UUID


class User(BaseModel):
    id: UUID
    hashed_username: str
    hashed_password: str
