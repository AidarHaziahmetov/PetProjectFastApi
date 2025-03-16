from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import async_engine
from app.main import app
from app.models.user import User
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session:
        await init_db(session)
        yield session
        statement = delete(User)
        await session.exec(statement)
        await session.commit()


@pytest.fixture(scope="module")
async def client() -> AsyncGenerator[TestClient, None]:
    async with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
async def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return await get_superuser_token_headers(client)


@pytest.fixture(scope="module")
async def normal_user_token_headers(
    client: TestClient, db: AsyncSession
) -> dict[str, str]:
    return await authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
