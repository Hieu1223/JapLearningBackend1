from uuid import UUID
from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException

from ..database import SessionDep
from ..security.auth import CurrentUser

from .controller import UserController
from .schema import (
    RegisterRequest,
    UserResponse,
    UpdateUserRequest,
    UpdateUserPartialRequest,
)

router = APIRouter(tags=["User Management"])


# 🔹 REGISTER
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_route(
    req: RegisterRequest,
    session: SessionDep
):
    return UserController.register_user(session, req)


# 🔹 CHECK (used by your frontend)
@router.get("/check", response_model=UserResponse)
def check_valid(user: CurrentUser):
    return user


# 🔹 GET CURRENT USER
@router.get("/me", response_model=UserResponse)
def get_me(user: CurrentUser):
    return user


# 🔹 GET USER BY ID
@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    session: SessionDep
):
    return UserController.get_user_or_404(session, user_id)


# 🔹 LIST USERS
@router.get("/", response_model=list[UserResponse])
def list_users(
    session: SessionDep,
    offset: int = 0,
    limit: int = 50
):
    return UserController.get_users(session, offset, limit)


# 🔹 UPDATE (PUT)
@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    req: UpdateUserRequest,
    session: SessionDep,
    user: CurrentUser,
):
    # 🔐 Prevent editing others
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return UserController.update_user(
        session,
        user_id,
        display_name=req.display_name,
    )


# 🔹 PARTIAL UPDATE (PATCH)
@router.patch("/{user_id}", response_model=UserResponse)
def update_user_partial(
    user_id: UUID,
    req: UpdateUserPartialRequest,
    session: SessionDep,
    user: CurrentUser,
):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return UserController.update_user_partial(
        session,
        user_id,
        req.model_dump(exclude_unset=True),
    )


# 🔹 DELETE
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    session: SessionDep,
    user: CurrentUser,
):
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    deleted = UserController.delete_user(session, user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")

    return None