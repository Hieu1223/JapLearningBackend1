from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4

class AuthUser(SQLModel, table=True):
    """Internal table for credentials only."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True)
    hashed_password: str = Field()
    # Link to your main User/Profile table
    user_id: UUID = Field(foreign_key="user.id", unique=True) 
