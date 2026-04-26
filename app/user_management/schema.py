from typing import Optional
from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel


# 🔹 REQUEST: Register
class RegisterRequest(SQLModel):
    username: str
    password: str
    display_name: Optional[str] = None


# 🔹 RESPONSE: Public User (safe to expose)
class UserResponse(SQLModel):
    id: UUID
    display_name: Optional[str]
    created_at: datetime
    updated_at: datetime


# 🔹 RESPONSE: User (with optional email if you later add it)
class UserWithEmailResponse(UserResponse):
    email: Optional[str] = None


# 🔹 UPDATE (PUT - full update)
class UpdateUserRequest(SQLModel):
    display_name: Optional[str] = None


# 🔹 PARTIAL UPDATE (PATCH)
class UpdateUserPartialRequest(SQLModel):
    display_name: Optional[str] = None