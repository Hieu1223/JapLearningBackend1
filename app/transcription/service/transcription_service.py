import json
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import Session, select
from fastapi import BackgroundTasks

from ...database import (
    get_user_history,  # noqa: F401  (kept for backwards ref; not used by routes)
    Video,
)
from ...database.transcription.schema import (
    Transcript,
    TranscriptStatus,
    TranscriptDetailResponse,
)
from ..schemas.transcription_request import (
    TranscriptionJobResponse,
    TranscriptionListResponse,
    TranscriptionListItem,
    VisitedVideoListResponse,
    VisitedVideoResponse,
)
from ..pipeline.transcribe_pipeline import transcribe_upload
from ...database.transcription.queries import (
    get_video_by_id,
    get_latest_transcript_for_video,
    get_transcript_by_id,
    get_video_progress,
    save_video_progress,
)
from ...database.transcription.queries import (
    list_transcripts_for_video,
    get_visited_videos,
)


class TranscriptionService:

    def _build_detail(self, v: Video, t: Transcript | None) -> TranscriptDetailResponse:
        status = t.status if t is not None else v.status
        done = status == TranscriptStatus.Finish.value
        msg = TranscriptStatus(status).name

        data = None
        if done and t and t.transcript_data:
            from ...database.transcription.schema import TranscriptResult
            payload = json.loads(t.transcript_data)
            data = TranscriptResult(**payload) if payload.get("segments") else None

        return TranscriptDetailResponse(
            id=t.id if t else v.id,
            status=status,
            done=done,
            msg=msg,
            data=data,
        )

    def submit_job(
        self,
        session: Session,
        video_id: UUID,
        user_id: UUID,
        background_tasks: BackgroundTasks,
    ) -> TranscriptionJobResponse:
        video = get_video_by_id(session, video_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")

        # One transcription attempt per video; reuse the latest if it exists.
        transcript = get_latest_transcript_for_video(session, video_id)
        if not transcript:
            transcript = Transcript(video_id=video.id, transcribed_by=user_id)
            session.add(transcript)
            session.commit()
            session.refresh(transcript)

        # Re-queue if not already finished.
        if video.status != TranscriptStatus.Finish.value:
            video.status = TranscriptStatus.InQueue.value
            session.add(video)
            session.commit()

            background_tasks.add_task(
                transcribe_upload, video.resource_id, user_id, transcript.id
            )

        return TranscriptionJobResponse(
            transcript_id=transcript.id,
            success=True,
        )

    def list_transcriptions(
        self,
        session: Session,
        video_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> TranscriptionListResponse:
        v = get_video_by_id(session, video_id)
        if not v:
            return TranscriptionListResponse(items=[], total=0)
        transcripts = list_transcripts_for_video(session, video_id, limit, offset)
        items = [
            TranscriptionListItem(
                transcript_id=t.id,
                video_id=v.id,
                original_source=v.original_source,
                resource_id=v.resource_id,
                name=v.name,
                thumbnail_url=v.thumbnail_url,
                status=t.status,
                done=t.status == TranscriptStatus.Finish.value,
                msg=TranscriptStatus(t.status).name,
            )
            for t in transcripts
        ]
        return TranscriptionListResponse(items=items, total=len(items))

    def poll_transcription(
        self,
        session: Session,
        transcript_id: UUID,
    ) -> TranscriptDetailResponse:
        t = get_transcript_by_id(session, transcript_id)
        if not t:
            raise ValueError(f"Transcript {transcript_id} not found")
        v = get_video_by_id(session, t.video_id) if t.video_id else None
        if not v:
            raise ValueError(f"Video for transcript {transcript_id} not found")
        return self._build_detail(v, t)

    def get_visited_videos(
        self,
        session: Session,
        user_id: UUID,
    ) -> VisitedVideoListResponse:
        rows = get_visited_videos(session, user_id)
        items = [
            VisitedVideoResponse(
                video_id=vp.video_id,
                name=v.name if v else None,
                thumbnail_url=v.thumbnail_url if v else None,
                original_source=v.original_source if v else None,
                resource_id=v.resource_id if v else None,
                progress=vp.progress,
                updated_at=vp.updated_at,
                status=v.status if v else 0,
                is_transcribed=(v.status == TranscriptStatus.Finish.value) if v else False,
            )
            for vp, v in rows
        ]
        return VisitedVideoListResponse(items=items, total=len(items))
