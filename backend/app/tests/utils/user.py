from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.crud.user import create_user, get_user_by_email, update_user
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.tests.utils.utils import random_email, random_lower_string


async def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    data = {"username": email, "password": password}

    r = await client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


async def create_random_user(db: AsyncSession) -> User:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = await create_user(session=db, user_create=user_in)
    return user


async def authentication_token_from_email(
    *, client: TestClient, email: str, db: AsyncSession
) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = await get_user_by_email(session=db, email=email)
    if not user:
        user_in_create = UserCreate(email=email, password=password)
        user = await create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        if not user.id:
            raise Exception("User id not set")
        user = await update_user(session=db, db_user=user, user_in=user_in_update)

    return await user_authentication_headers(
        client=client, email=email, password=password
    )
