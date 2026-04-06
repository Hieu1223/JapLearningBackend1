from fastapi import APIRouter,Depends
from typing import Annotated
from .look_up import look_up


router = APIRouter(tags=["look_up"])    

@router.get("/look_up/{word}")
async def look_up_endpoint(word: Annotated[str, Depends(look_up)]):
    return word