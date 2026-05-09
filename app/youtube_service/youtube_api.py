import httpx
from typing import List, Optional
from fastapi import HTTPException

from yt_dlp import YoutubeDL
import os

from .schema import VideoInfo, VideoPreview, ChannelInfo, ChannelPreview
from .key_manager import key_manager

proxy_url = os.getenv("HTTP_PROXY")

YDL_OPTS_VIDEO = {
    "quiet": True,
    "proxy": proxy_url,
}

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _duration_from_iso(iso: str) -> Optional[str]:
    """Convert ISO 8601 duration (PT1H2M3S) to human-readable (1:02:03)."""
    import re
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not match:
        return None
    h, m, s = (int(x or 0) for x in match.groups())
    if h:
        return f"{h}:{m:02}:{s:02}"
    return f"{m}:{s:02}"


def _fetch_video_details(video_ids: list[str], api_key: str) -> dict[str, dict]:
    """
    Batch-fetch snippet + contentDetails + statistics for a list of video IDs.
    Returns a dict keyed by video id.
    """
    resp = httpx.get(_VIDEOS_URL, params={
        "part": "snippet,contentDetails,statistics",
        "id": ",".join(video_ids),
        "key": api_key,
    }, timeout=10)
    resp.raise_for_status()
    return {item["id"]: item for item in resp.json().get("items", [])}


def search_youtube(query: str, limit: int = 10) -> List[VideoPreview]:
    max_retries = 2  # allow one key rotation on quota error

    for attempt in range(max_retries + 1):
        api_key = key_manager.get_current_key()
        try:
            # 1. Search for video IDs + basic snippet
            search_resp = httpx.get(_SEARCH_URL, params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": limit,
                "key": api_key,
            }, timeout=10)

            if search_resp.status_code == 403:
                data = search_resp.json()
                reason = (
                    data.get("error", {})
                    .get("errors", [{}])[0]
                    .get("reason", "")
                )
                if reason in ("quotaExceeded", "dailyLimitExceeded"):
                    key_manager.mark_exhausted(api_key)
                    continue  # retry with next key
                raise HTTPException(403, detail=data.get("error", {}).get("message", "Forbidden"))

            search_resp.raise_for_status()
            search_data = search_resp.json()
            items = search_data.get("items", [])

            if not items:
                return []

            # 2. Batch-fetch durations + view counts (search results don't include these)
            video_ids = [item["id"]["videoId"] for item in items]
            details = _fetch_video_details(video_ids, api_key)

            # 3. Build VideoPreview list
            results: List[VideoPreview] = []
            for item in items:
                vid_id = item["id"]["videoId"]
                snippet = item["snippet"]
                detail = details.get(vid_id, {})
                content = detail.get("contentDetails", {})
                stats = detail.get("statistics", {})

                thumbnails = snippet.get("thumbnails", {})
                thumbnail_url = (
                    thumbnails.get("maxres")
                    or thumbnails.get("high")
                    or thumbnails.get("medium")
                    or thumbnails.get("default")
                    or {}
                ).get("url")

                results.append(VideoPreview(
                    id=vid_id,
                    title=snippet.get("title", ""),
                    thumbnail_url=thumbnail_url,
                    channel=ChannelPreview(
                        id=snippet.get("channelId", ""),
                        name=snippet.get("channelTitle"),
                        url=f"https://www.youtube.com/channel/{snippet.get('channelId', '')}",
                    ),
                    duration=_duration_from_iso(content.get("duration")),
                    description=(
                        snippet.get("description", "")[:150] + "..."
                        if len(snippet.get("description", "")) > 150
                        else snippet.get("description")
                    ),
                    view_count=int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
                ))

            # Round-robin: advance to next key after a successful call
            key_manager.advance()
            return results

        except httpx.HTTPStatusError as e:
            raise HTTPException(502, detail=f"YouTube API error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(502, detail=f"Network error reaching YouTube API: {str(e)}")

    raise HTTPException(429, detail="All YouTube API keys are exhausted for today.")


def get_video_by_id(video_id: str) -> Optional[VideoInfo]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with YoutubeDL(YDL_OPTS_VIDEO) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as err:
        raise RuntimeError(f"yt-dlp video fetch failed: {str(err)}")

    if not info:
        return None

    return VideoInfo.fromYdtlJson(info)