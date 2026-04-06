from fastapi import APIRouter, Depends
from ..security import scheme
import re
from typing import Annotated
from .tokenize import TokenList,tokenize

router = APIRouter(tags=["tokenization"])

@router.get("/tokenize/{text}")
async def tokenize_endpoint(text: Annotated[str, Depends(tokenize)], token = Depends(scheme)) -> TokenList:
    return  text

