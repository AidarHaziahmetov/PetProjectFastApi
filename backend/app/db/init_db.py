from sqlmodel import select

from app.core.config import settings
from app.crud.user import create_user
from app.models.user import User
from app.schemas.user import UserCreate

# from app.db.session import async_engine


async def init_db(session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # async with async_engine.begin() as conn:
    #    await conn.run_sync(SQLModel.metadata.create_all)

    result = await session.execute(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    )
    user = result.scalars().first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = await create_user(session=session, user_create=user_in)
