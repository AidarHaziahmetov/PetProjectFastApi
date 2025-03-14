import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.sql import func, select

from app.api.v1.deps import (
    AsyncSessionDep,
    CurrentUserAsync,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.crud.user import (
    create_user,
    get_user_by_email,
    update_user,
)
from app.crud.user import (
    read_user_by_id as read_user_by_id_crud,
)
from app.crud.user import (
    read_users as read_users_crud,
)
from app.models.user import User
from app.schemas.common import ApiMessage
from app.schemas.user import (
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils.email import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
async def read_users(session: AsyncSessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    users = await read_users_crud(session=session, skip=skip, limit=limit)
    count_statement = select(func.count()).select_from(User)
    count = await session.scalar(count_statement)
    users_list = [UserPublic.model_validate(user) for user in users]
    return UsersPublic(data=users_list, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
async def create_new_user(*, session: AsyncSessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = await get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = await create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    *, session: AsyncSessionDep, user_in: UserUpdateMe, current_user: CurrentUserAsync
) -> Any:
    """
    Update own user.
    """
    if user_in.email:
        existing_user = await get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=ApiMessage)
async def update_password_me(
    *, session: AsyncSessionDep, body: UpdatePassword, current_user: CurrentUserAsync
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    await session.commit()
    return ApiMessage(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUserAsync) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=ApiMessage)
async def delete_user_me(
    session: AsyncSessionDep, current_user: CurrentUserAsync
) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    await session.delete(current_user)
    await session.commit()
    return ApiMessage(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
async def register_user(session: AsyncSessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = await get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = await create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: uuid.UUID, session: AsyncSessionDep, current_user: CurrentUserAsync
) -> Any:
    """
    Get a specific user by id.
    """
    user = await read_user_by_id_crud(session=session, user_id=user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
async def update_user_by_id(
    *,
    session: AsyncSessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """
    db_user = await session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = await get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    return await update_user(session=session, db_user=db_user, user_in=user_in)


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(
    session: AsyncSessionDep, current_user: CurrentUserAsync, user_id: uuid.UUID
) -> ApiMessage:
    """
    Delete a user.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    await session.delete(user)
    await session.commit()
    return ApiMessage(message="User deleted successfully")
