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

router = APIRouter(tags=["User Management"], prefix='/user')

_container = Container()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["User Management"], description="Register a new user account from the supplied credentials and profile")
def register_route(
    req: RegisterRequest,
):
    session = get_db_session()
    return _container.user_service.register_user(session, req)


@router.get("/check", response_model=UserResponse, tags=["User Management"], description="Validate the current access token and return the authenticated user")
def check_valid(user: CurrentUser):
    session = get_db_session()
    return _container.user_service.get_user_or_404(session, user)


@router.get("/me", response_model=UserResponse, tags=["User Management"], description="Return the profile of the currently authenticated user")
def get_me(user: CurrentUser):
    session = get_db_session()
    return _container.user_service.get_user_or_404(session, user)


# ── User Settings ──────────────────────────────────────────────────────────────

@router.get("/settings", response_model=UserSettingsResponse, tags=["User Management"], description="Return the current user's saved settings")
def get_user_settings(
    user: CurrentUser,
):
    session = get_db_session()
    settings = _container.user_service.get_user_settings(session, user)
    return UserSettingsResponse(settings=settings)


@router.post("/settings", response_model=UserSettingsResponse, tags=["User Management"], description="Save (create or replace) the current user's settings")
def save_user_settings(
    req: SaveUserSettingsRequest,
    user: CurrentUser,
):
    session = get_db_session()
    settings = _container.user_service.save_user_settings(session, user, req.settings)
    return UserSettingsResponse(settings=settings)


@router.get("/{user_id}", response_model=UserResponse, tags=["User Management"], description="Fetch a single user's public profile by user id")
def get_user(
    user_id: UUID,
):
    session = get_db_session()
    return _container.user_service.get_user_or_404(session, user_id)


@router.get("/", response_model=list[UserResponse], tags=["User Management"], description="List users with pagination support")
def list_users(
    user: CurrentUser,
    offset: int = 0,
    limit: int = 50
):
    session = get_db_session()
    return _container.user_service.get_users(session, offset, limit)


@router.put("/{user_id}", response_model=UserResponse, tags=["User Management"], description="Fully replace a user's mutable profile fields; only the owner may perform this")
def update_user(
    user_id: UUID,
    req: UpdateUserRequest,
    user: CurrentUser,
):
    if user != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = get_db_session()
    return _container.user_service.update_user(
        session,
        user_id,
        display_name=req.display_name,
    )


@router.patch("/{user_id}", response_model=UserResponse, tags=["User Management"], description="Partially update a user's profile with only the supplied fields; only the owner may perform this")
def update_user_partial(
    user_id: UUID,
    req: UpdateUserPartialRequest,
    user: CurrentUser,
):
    if user != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = get_db_session()
    return _container.user_service.update_user_partial(
        session,
        user_id,
        req.model_dump(exclude_unset=True),
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["User Management"], description="Delete a user account and all of its associated data; only the owner may perform this")
def delete_user(
    user_id: UUID,
    user: CurrentUser,
):
    if user != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    session = get_db_session()
    deleted = _container.user_service.delete_user(session, user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    return None
