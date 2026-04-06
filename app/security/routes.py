from typing import Annotated
from fastapi import Depends, APIRouter
from fastapi.security import OAuth2PasswordBearer,OAuth2PasswordRequestForm
from .security import scheme

router = APIRouter(tags=["security"])

@router.get("/")
async def root(token: Annotated[str, Depends(scheme)]):
    return {"message": "Hello World", "token": token}

@router.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    return {"access_token": "1", "token_type": "bearer"}