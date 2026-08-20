from fastapi import APIRouter, HTTPException
from uuid import UUID

from .yt_dl_service import get_preview_video
from .schema import VideoPreview, VideoProgressResponse, SaveVideoProgressRequest
from ..security.auth import CurrentUser
from ..container import Container, get_db_session
from ..database.transcription.queries import (
    get_video_progress,
    save_video_progress,
    get_or_create_video_from_preview,
    has_transcript_for_video,
)

router = APIRouter(tags=["YouTube"])

_container = Container()


@router.get("/video/{video_id}", response_model=VideoPreview, tags=["YouTube"], description="Preview a YouTube video and return its metadata plus the app-internal video uuid to use for transcription jobs")
def preview_video(video_id: str):
    video = get_preview_video(video_id)

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Ensure an app Video row exists so transcription jobs have a stable uuid.
    session = get_db_session()
    db_video = get_or_create_video_from_preview(
        session,
        resource_id=video_id,
        name=video.title,
        thumbnail_url=video.thumbnail_url,
        resource_url=f"https://www.youtube.com/watch?v={video_id}",
        video_data=video.model_dump(),
    )
    # The DB-stored uuid (distinct from the YouTube resource id).
    video.app_video_id = db_video.id
    video.has_transcript = has_transcript_for_video(session, db_video.id)
    return video


# ── Video Progress ───────────────────────────────────────────────────────────────

@router.get("/progress", response_model=VideoProgressResponse | None, tags=["YouTube"], description="Return the saved playback progress for a video (by app video id), if any")
async def get_video_progress_route(
    video_id: UUID,
    user: CurrentUser,
):
    session = get_db_session()
    progress = get_video_progress(session, user, video_id)
    if not progress:
        return None
    return VideoProgressResponse(
        video_id=progress.video_id,
        progress=progress.progress,
        updated_at=progress.updated_at,
    )


@router.post("/progress", response_model=VideoProgressResponse, tags=["YouTube"], description="Save the current playback progress for a video (by app video id) for the current user")
async def save_video_progress_route(
    req: SaveVideoProgressRequest,
    user: CurrentUser,
):
    session = get_db_session()
    progress = save_video_progress(session, user, req.video_id, req.progress)
    return VideoProgressResponse(
        video_id=progress.video_id,
        progress=progress.progress,
        updated_at=progress.updated_at,
    )
