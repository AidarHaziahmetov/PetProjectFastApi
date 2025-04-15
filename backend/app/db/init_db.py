from app.core.config import settings
from app.repositories.user import UserRepository
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

    result = await UserRepository(session).get_by_email(settings.FIRST_SUPERUSER)
    if not result:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        await UserRepository(session).create(user_in)
