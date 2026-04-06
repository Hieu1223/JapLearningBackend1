from pydantic import BaseModel
from typing import Optional,List
from datetime import datetime



class ChannelPreview(BaseModel):
    id: str
    name: Optional[str]
    url: Optional[str]

    @staticmethod
    def fromYtdlFlatJson(data: dict) -> "ChannelPreview":
        return ChannelPreview(
            id=data.get("channel_id") or data.get("uploader_id"),
            name=data.get("channel") or data.get("uploader"),
            url=data.get("channel_url") or data.get("uploader_url"),
        )
    


class VideoPreview(BaseModel):
    id: str
    title: str
    thumbnail_url: Optional[str]
    channel: ChannelPreview
    duration: Optional[str]
    description: Optional[str]
    view_count: Optional[int] = None
    @staticmethod
    def _short_description(data: dict) -> Optional[str]:
        desc = data.get("description")
        if not desc:
            return None
        return desc[:150] + "..." if len(desc) > 150 else desc

    @staticmethod
    def _get_duration(data: dict) -> Optional[str]:
        # 1. best case
        if data.get("duration_string"):
            return data["duration_string"]

        # 2. fallback → convert seconds
        seconds = data.get("duration")
        if not seconds:
            return None

        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)

        return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

    @staticmethod
    def fromYtdlFlatJson(data: dict) -> "VideoPreview":
        return VideoPreview(
            id=data.get("id"),
            title=data.get("title"),
            thumbnail_url=(
                data.get("thumbnail") or
                (data.get("thumbnails")[-1]["url"] if data.get("thumbnails") else None)
            ),
            channel=ChannelPreview.fromYtdlFlatJson(data),
            duration=VideoPreview._get_duration(data),
            description=VideoPreview._short_description(data),
            view_count=data.get("view_count")
        )

class ChannelInfo(BaseModel):
    id: str
    name: Optional[str]
    url: Optional[str]
    follower_count: Optional[int]
    is_verified: Optional[bool]
    description: Optional[str]

    @staticmethod
    def fromYtdlJson(data: dict) -> "ChannelInfo":
        return ChannelInfo(
            id=data.get("channel_id") or data.get("uploader_id"),
            name=data.get("channel") or data.get("uploader"),
            url=data.get("channel_url") or data.get("uploader_url"),
            follower_count=data.get("channel_follower_count"),
            is_verified=data.get("channel_is_verified"),
            description=data.get("description")  # ⚠️ often NOT channel description
        )





class VideoInfo(BaseModel):
    id: str
    title: str
    thumbnail_url: str
    channel : ChannelInfo
    duration: float
    view_count: int
    upload_date: Optional[str]   # formatted YYYY-MM-DD
    description: Optional[str]

    @staticmethod
    def parse_upload_date(date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        try:
            # yt-dlp format: YYYYMMDD
            dt = datetime.strptime(date_str, "%Y%m%d")
            return dt.strftime("%Y-%m-%d")  # normalize
        except Exception:
            return None

    @staticmethod
    def fromYdtlJson(data: dict) -> "VideoInfo":
        return VideoInfo(
            id=data.get("id"),
            title=data.get("title"),
            thumbnail_url=(
                data.get("thumbnail") or
                (data.get("thumbnails")[-1]["url"] if data.get("thumbnails") else None)
            ),
            channel=ChannelInfo.fromYtdlJson(data),
            duration=float(data.get("duration") or 0),
            view_count=int(data.get("view_count") or 0),
            upload_date=VideoInfo.parse_upload_date(data.get("upload_date")),
            description=data.get("description")
        )


class ChannelVideosResponse(BaseModel):
    channel: ChannelInfo
    videos: List[VideoPreview]