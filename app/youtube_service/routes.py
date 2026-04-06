# routers/youtube_router.py

from fastapi import APIRouter, Query, HTTPException
from typing import List

from .yt_dl_service import *
from .schema import *

router = APIRouter(prefix="/youtube", tags=["YouTube"])


@router.get("/search", response_model=List[VideoPreview])
def search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50)
):
    results = search_youtube(q, limit)

    if not results:
        raise HTTPException(status_code=404, detail="No results found")

    return results


@router.get("/video/{video_id}", response_model=VideoInfo)
def get_video(video_id: str):
    video = get_video_by_id(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return video
