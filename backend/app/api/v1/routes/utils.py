from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr

from app.api.v1.deps import get_current_active_superuser
from app.schemas.common import ApiMessage
from app.utils.email import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> ApiMessage:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return ApiMessage(message="Test email sent")


@router.get("/health-check/")
async def health_check() -> bool:
    return True
