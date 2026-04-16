from typing import Annotated
from fastapi import Depends, APIRouter
from ..database.user import User
from ..database import SessionDep
from fastapi.exceptions import HTTPException
from .schema import RegisterRequest
from .controller import UserController

router = APIRouter(tags=["User Management"])

@router.post("/register", response_model=User)
def register_route(
    req: RegisterRequest, 
    session: SessionDep
):
    """
    Register a new user and create their authentication credentials.
    """
    return UserController.register_user(session, req)