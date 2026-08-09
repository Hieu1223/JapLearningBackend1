from fastapi import APIRouter, HTTPException

from .yt_dl_service import get_preview_video
from .schema import VideoPreview

router = APIRouter(tags=["YouTube"])


@router.get("/video/{video_id}", response_model=VideoPreview, tags=["YouTube"], description="Return preview metadata (title, channel, thumbnail) for a YouTube video by id")
def preview_video(video_id: str):
    video = get_preview_video(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return video
