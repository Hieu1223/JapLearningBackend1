from pydantic import BaseModel

class TokenList(BaseModel):
    tokens : list[str]