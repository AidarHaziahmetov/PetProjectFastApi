import uuid
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def create_user(*, session: AsyncSession, user_create: UserCreate) -> User:
    """Асинхронное создание пользователя"""
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def update_user(
    *, session: AsyncSession, db_user: User, user_in: UserUpdate
) -> Any:
    """Асинхронное обновление пользователя"""
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def get_user_by_email(*, session: AsyncSession, email: str) -> User | None:
    """Асинхронное получение пользователя по email"""
    statement = select(User).where(User.email == email)
    result = await session.exec(statement)
    user = result.first()
    return user


async def authenticate(
    *, session: AsyncSession, email: str, password: str
) -> User | None:
    """Асинхронная аутентификация пользователя"""
    db_user = await get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


async def read_users(
    *, session: AsyncSession, skip: int = 0, limit: int = 100
) -> list[User]:
    statement = select(User).offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def read_user_by_id(*, session: AsyncSession, user_id: uuid.UUID) -> User | None:
    statement = select(User).where(User.id == user_id)
    result = await session.exec(statement)
    return result.first()
