from yt_dlp import YoutubeDL
from typing import List, Optional
from fastapi.exceptions import HTTPException
from .schema import VideoInfo, VideoPreview,ChannelInfo,ChannelVideosResponse,ChannelPreview

import os

proxy_url = os.getenv("HTTP_PROXY") 

YDL_OPTS_SEARCH = {
    "quiet": True,
    "extract_flat": True,
    "proxy": proxy_url,
}

YDL_OPTS_VIDEO = {
    "quiet": True,
    "proxy": proxy_url,
}


def search_youtube(query: str, limit: int = 10) -> List[VideoPreview]:
    search_query = f"ytsearch{limit}:{query}"

    try:
        with YoutubeDL(YDL_OPTS_SEARCH) as ydl:
            info = ydl.extract_info(search_query, download=False)
    except Exception as err:
        raise RuntimeError(f"yt-dlp search failed: {str(err)}")

    entries = info.get("entries") or []

    results: List[VideoPreview] = []
    for entry in entries:
        if not entry:
            continue
        try:
            results.append(VideoPreview.fromYtdlFlatJson(entry))
        except Exception:
            continue  # skip malformed entries silently

    return results


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



