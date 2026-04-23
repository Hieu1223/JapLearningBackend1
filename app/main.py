from dotenv import load_dotenv
load_dotenv()
import asyncio
import sys
from .transcription import recover_orphaned_transcript
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from fastapi import FastAPI
from .routes import *
from .user_management import *
from .database import create_db_and_tables,Session, engine

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
    
    with Session(engine) as session:
        recover_orphaned_transcript(session)

@app.get("/ping")
def ping():
    return {"status": "ok"}

app.include_router(tokenization_router, prefix="/tokenization")
app.include_router(security_router, tags=["Security"])
app.include_router(user_management_router, tags=['User Management'])
app.include_router(transcription_router, prefix="/transcription")
app.include_router(youtube_router, prefix='/youtube')
app.include_router(flashcard_router, prefix='/flashcard', tags=["Flashcard"])
app.include_router(manga_reader_router, prefix='/manga')