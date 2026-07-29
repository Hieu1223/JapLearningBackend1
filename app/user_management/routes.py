from uuid import UUID
from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException

from ..security.auth import CurrentUser
from ..container import Container, get_db_session
from .schema import (
    RegisterRequest,
    UserResponse,
    UpdateUserRequest,
    UpdateUserPartialRequest,
    UserSettingsResponse,
    SaveUserSettingsRequest,
)

router = APIRouter(tags=["User Management"])

_container = Container()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_route(
    req: RegisterRequest,
):
    session = get_db_session()
    return _container.user_service.register_user(session, req)


@router.get("/check", response_model=UserResponse)
def check_valid(user: CurrentUser):
    return user


@router.get("/me", response_model=UserResponse)
def get_me(user: CurrentUser):
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
):
    session = get_db_session()
    return _container.user_service.get_user_or_404(session, user_id)


@router.get("/", response_model=list[UserResponse])
def list_users(
    offset: int = 0,
    limit: int = 50
):
    session = get_db_session()
    return _container.user_service.get_users(session, offset, limit)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    req: UpdateUserRequest,
    user: CurrentUser,
):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = get_db_session()
    return _container.user_service.update_user(
        session,
        user_id,
        display_name=req.display_name,
    )


@router.patch("/{user_id}", response_model=UserResponse)
def update_user_partial(
    user_id: UUID,
    req: UpdateUserPartialRequest,
    user: CurrentUser,
):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = get_db_session()
    return _container.user_service.update_user_partial(
        session,
        user_id,
        req.model_dump(exclude_unset=True),
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    user: CurrentUser,
):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = get_db_session()
    deleted = _container.user_service.delete_user(session, user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    return None


# ── User Settings ──────────────────────────────────────────────────────────────

@router.get("/settings", response_model=UserSettingsResponse)
def get_user_settings(
    user: CurrentUser,
):
    session = get_db_session()
    settings = _container.user_service.get_user_settings(session, user.id)
    return UserSettingsResponse(settings=settings)


@router.post("/settings", response_model=UserSettingsResponse)
def save_user_settings(
    req: SaveUserSettingsRequest,
    user: CurrentUser,
):
    session = get_db_session()
    settings = _container.user_service.save_user_settings(session, user.id, req.settings)
    return UserSettingsResponse(settings=settings)