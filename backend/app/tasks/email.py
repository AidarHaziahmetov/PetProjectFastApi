import logging
from typing import Any

from app.core.celery_app import celery_app
from app.utils.email import (
    EmailData,
    generate_new_account_email,
    generate_reset_password_email,
    generate_test_email,
    send_email,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@celery_app.task
def send_test_email_task(email_to: str) -> dict[str, Any]:
    """
    Задача Celery для отправки тестового письма
    """
    email_data: EmailData = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return {"email": email_to, "message": "Test email sent"}


@celery_app.task
def send_reset_password_email_task(
    email_to: str, email: str, token: str
) -> dict[str, Any]:
    """
    Задача Celery для отправки письма восстановления пароля
    """
    email_data: EmailData = generate_reset_password_email(
        email_to=email_to, email=email, token=token
    )
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return {"email": email_to, "message": "Reset password email sent"}


@celery_app.task
def send_new_account_email_task(
    email_to: str, username: str, password: str
) -> dict[str, Any]:
    """
    Задача Celery для отправки письма о создании нового аккаунта
    """
    email_data: EmailData = generate_new_account_email(
        email_to=email_to, username=username, password=password
    )
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return {"email": email_to, "message": "New account email sent"}


@celery_app.task
def send_email_task(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> dict[str, Any]:
    """
    Общая задача Celery для отправки любых писем
    """
    send_email(
        email_to=email_to,
        subject=subject,
        html_content=html_content,
    )
    return {"email": email_to, "message": "Email sent"}
