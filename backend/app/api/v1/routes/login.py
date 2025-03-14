from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.deps import (
    AsyncSessionDep,
    CurrentUserAsync,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.crud.user import authenticate, get_user_by_email
from app.schemas.auth import NewPassword, Token
from app.schemas.common import ApiMessage
from app.schemas.user import UserPublic
from app.tasks.email import send_reset_password_email_task
from app.utils.email import generate_reset_password_email
from app.utils.security import (
    generate_password_reset_token,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
async def login_access_token(
    session: AsyncSessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = await authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = Token(
        access_token=create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )
    print(token)
    return token


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUserAsync) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
async def recover_password(email: str, session: AsyncSessionDep) -> ApiMessage:
    """
    Password Recovery
    """
    user = await get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    send_reset_password_email_task.delay(
        email_to=user.email,
        email=email,
        token=password_reset_token,
    )
    return ApiMessage(message="Password recovery email sent")


@router.post("/reset-password/")
async def reset_password(session: AsyncSessionDep, body: NewPassword) -> ApiMessage:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    await session.commit()
    return ApiMessage(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
async def recover_password_html_content(email: str, session: AsyncSessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = await get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
