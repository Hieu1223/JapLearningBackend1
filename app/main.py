from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from typing import Annotated
from fastapi import FastAPI
from .routes import *
from .transcription import create_db_and_tables
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],           # Allowed domains
    allow_credentials=True,         # Support cookies/auth headers
    allow_methods=["*"],             # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],             # Allow all request headers
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/ping")
def ping():
    return {"status": "ok"}

app.include_router(tokenization_router, prefix="/tokenization")
app.include_router(security_router)
app.include_router(transcription_router, prefix="/transcription")
app.include_router(youtube_router, prefix='/youtube')
app.include_router(flashcard_router, prefix='/flashcard')