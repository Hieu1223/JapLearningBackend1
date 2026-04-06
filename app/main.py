from dotenv import load_dotenv

load_dotenv()

from typing import Annotated
from fastapi import FastAPI
from .routes import *
from .transcription import create_db_and_tables
app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.include_router(tokenization_router, prefix="/tokenization")
app.include_router(security_router)
app.include_router(transcription_router, prefix="/transcription")
app.include_router(look_up_router, prefix="/look_up")
app.include_router(youtube_router, prefix='/youtube')