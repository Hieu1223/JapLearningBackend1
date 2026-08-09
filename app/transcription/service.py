import json
from uuid import UUID
from datetime import datetime, timezone
from sqlmodel import Session, select
from fastapi import BackgroundTasks

from ..database import (
    check_exist_and_create_transcription_entry,
    get_user_history,
    remove_history_entry,
    update_status,
    TranscriptionHistory,
)
from ..database.transcription.schema import (
    Transcript,
    TranscriptStatus,
    TranscriptResult,
    TranscriptDetailResponse,
    UserHistoryListResponse,
    VideoProgress,
    VideoProgressResponse,
    VideoDetail,
)
from .schema import (
    TranscriptRequestResponse,
    YoutubeTranscriptRequestForm,
)
from .transcribe_pipeline import transcribe_upload
from ..database.transcription.queries import get_video_progress, save_video_progress


class TranscriptionService:
    
    def get_transcription_detail(self, session: Session, id: UUID) -> TranscriptDetailResponse:
        t = session.get(Transcript, id)
        if not t:
            raise ValueError(f"Transcript {id} not found")
        
        done = t.status == TranscriptStatus.Finish.value
        msg = TranscriptStatus(t.status).name
        
        data = None
        if done and t.data:
            data = TranscriptResult(**json.loads(t.data))
        
        video_data = {
            "id": t.resource_id,
            "title": t.name,
            "thumbnail_url": t.thumnail_url,
            "channel": None,
            "duration": None,
        }
        video_detail = VideoDetail.from_dict(video_data)
        
        individual_settings = None
        if t.individual_settings:
            individual_settings = json.loads(t.individual_settings)
        
        return TranscriptDetailResponse(
            id=t.id,
            original_source=t.original_source,
            thumnail_url=t.thumnail_url,
            resource_url=t.resource_url,
            resource_id=t.resource_id,
            status=t.status,
            done=done,
            msg=msg,
            video=video_detail,
            data=data,
            individual_settings=individual_settings,
        )
    
    def save_individual_settings(
        self,
        session: Session,
        transcript_id: UUID,
        user_id: UUID,
        settings: dict,
    ) -> dict:
        t = session.get(Transcript, transcript_id)
        if not t:
            raise ValueError(f"Transcript {transcript_id} not found")
        
        history_entry = session.exec(
            select(TranscriptionHistory).where(
                TranscriptionHistory.transcript_id == transcript_id,
            )
        ).first()
        
        if not history_entry or history_entry.user_id != user_id:
            raise ValueError("Unauthorized access to transcript settings")
        
        t.individual_settings = json.dumps(settings)
        session.add(t)
        session.commit()
        session.refresh(t)
        
        return {"success": True, "transcript_id": str(transcript_id)}
    
    def submit_transcription(
        self,
        session: Session,
        form: YoutubeTranscriptRequestForm,
        user_id: UUID,
        background_tasks: BackgroundTasks,
    ) -> TranscriptRequestResponse:
        info = check_exist_and_create_transcription_entry(session, form, user_id)
        
        if info.status == TranscriptStatus.InQueue.value:
            background_tasks.add_task(transcribe_upload, form, user_id)
        
        return TranscriptRequestResponse(transcript_id=info.id, success=True)
    
    def rerun_transcription(
        self,
        session: Session,
        id: UUID,
        user_id: UUID,
        background_tasks: BackgroundTasks,
    ) -> TranscriptRequestResponse:
        t = session.get(Transcript, id)
        if not t:
            raise ValueError(f"Transcript {id} not found")
        
        t.status = TranscriptStatus.InQueue.value
        session.add(t)
        session.commit()
        session.refresh(t)
        
        form = YoutubeTranscriptRequestForm(
            name=t.name,
            resource_id=t.resource_id,
            original_source=t.original_source,
            public=t.public,
            thumbnail_url=t.thumnail_url,
            resource_url=t.resource_url,
        )
        
        background_tasks.add_task(transcribe_upload, form, user_id)
        
        return TranscriptRequestResponse(transcript_id=id, success=True)
    
    def visit_video(
        self,
        session: Session,
        form: YoutubeTranscriptRequestForm,
        user_id: UUID,
    ) -> TranscriptDetailResponse:
        existing = session.exec(
            select(TranscriptionHistory).where(
                TranscriptionHistory.user_id == user_id,
                TranscriptionHistory.resource_id == form.resource_id,
            )
        ).first()
        
        if existing:
            existing.date_created = datetime.now(timezone.utc)
            session.add(existing)
            session.commit()
            session.refresh(existing)
        else:
            history_entry = TranscriptionHistory(
                user_id=user_id,
                resource_id=form.resource_id,
                name=form.name,
                thumbnail_url=form.thumbnail_url,
                original_source=form.original_source,
                resource_url=form.resource_url,
            )
            session.add(history_entry)
            session.commit()
            session.refresh(history_entry)
        
        t = session.get(Transcript, existing.transcript_id) if existing.transcript_id else None
        
        done = False
        msg = "NotTranscribed"
        data = None
        individual_settings = None
        
        video_data = {
            "id": existing.resource_id,
            "title": existing.name,
            "thumbnail_url": existing.thumbnail_url,
            "channel": None,
            "duration": None,
        }
        video_detail = VideoDetail.from_dict(video_data)
        
        if t:
            done = t.status == TranscriptStatus.Finish.value
            msg = TranscriptStatus(t.status).name
            if done and t.data:
                data = TranscriptResult(**json.loads(t.data))
            if t.individual_settings:
                individual_settings = json.loads(t.individual_settings)
        
        return TranscriptDetailResponse(
            id=t.id if t else existing.id,
            original_source=existing.original_source,
            thumnail_url=existing.thumbnail_url,
            resource_url=existing.resource_url,
            resource_id=existing.resource_id,
            status=t.status if t else 0,
            done=done,
            msg=msg,
            video=video_detail,
            data=data,
            individual_settings=individual_settings,
        )
    
    def get_history(self, session: Session, user_id: UUID) -> UserHistoryListResponse:
        return get_user_history(session, user_id)
    
    def delete_history_entry(self, session: Session, history_id: UUID, user_id: UUID) -> bool:
        return remove_history_entry(session, history_id, user_id)

    def get_video_progress(
        self,
        session: Session,
        user_id: UUID,
        resource_id: str,
        original_source: str,
    ) -> VideoProgressResponse | None:
        progress = get_video_progress(session, user_id, resource_id, original_source)
        if not progress:
            return None
        return VideoProgressResponse(
            resource_id=progress.resource_id,
            original_source=progress.original_source,
            current_page=progress.current_page,
            updated_at=progress.updated_at,
        )

    def save_video_progress(
        self,
        session: Session,
        user_id: UUID,
        resource_id: str,
        original_source: str,
        current_page: int,
    ) -> VideoProgressResponse:
        progress = save_video_progress(
            session, user_id, resource_id, original_source, current_page
        )
        return VideoProgressResponse(
            resource_id=progress.resource_id,
            original_source=progress.original_source,
            current_page=progress.current_page,
            updated_at=progress.updated_at,
        )