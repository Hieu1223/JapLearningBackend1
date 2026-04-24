from fastapi import APIRouter, Depends
from ..security import scheme
import re
from typing import Annotated
from .tokenize import TokenList,tokenize


router = APIRouter(tags=["tokenization"])


@router.get("/tokenize/{text}", response_model=TokenList)
async def tokenize_endpoint(
    tokens=Depends(tokenize),
    token=Depends(scheme)
):
    return TokenList(tokens=tokens)
