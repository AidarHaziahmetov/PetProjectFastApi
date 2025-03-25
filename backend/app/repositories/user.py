from uuid import UUID

from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserUpdate


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def create(self, user: UserCreate) -> User:
        db_obj = self.model.model_validate(
            user, update={"hashed_password": get_password_hash(user.password)}
        )
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(self, db_user: User, user: UserUpdate) -> User:
        user_data = user.model_dump(exclude_unset=True)
        extra_data = {}
        if "password" in user_data:
            password = user_data["password"]
            hashed_password = get_password_hash(password)
            extra_data["hashed_password"] = hashed_password
        db_user.sqlmodel_update(user_data, update=extra_data)
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return db_user

    async def get_by_email(self, email: str) -> User | None:
        query = select(self.model).where(self.model.email == email)
        result = await self.session.exec(query)
        return result.one_or_none()

    async def get_by_id(self, id: UUID) -> User | None:
        query = select(self.model).where(self.model.id == id)
        result = await self.session.exec(query)
        return result.one_or_none()

    async def list(
        self, skip: int | None = None, limit: int | None = None
    ) -> list[User]:
        query = select(self.model)
        if skip is not None:
            query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        result = await self.session.exec(query)
        return list(result.all())

    async def delete(self, id: UUID) -> None:
        query = delete(self.model).where(self.model.id == id)  # type: ignore
        await self.session.exec(query)  # type: ignore
        await self.session.commit()

    async def authenticate(self, email: str, password: str) -> User | None:
        """Асинхронная аутентификация пользователя"""
        db_user = await self.get_by_email(email=email)
        if not db_user:
            return None
        if not verify_password(password, db_user.hashed_password):
            return None
        return db_user
