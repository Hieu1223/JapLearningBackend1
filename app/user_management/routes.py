from typing import Annotated
from fastapi import Depends, APIRouter
from fastapi.security import OAuth2PasswordBearer,OAuth2PasswordRequestForm

router = APIRouter(tags=["user_management"])