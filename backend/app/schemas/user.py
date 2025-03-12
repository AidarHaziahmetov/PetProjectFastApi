from uuid import UUID

from pydantic import EmailStr
from sqlmodel import SQLModel


# Базовая схема с общими свойствами
class UserBase(SQLModel):
    email: str
    full_name: str | None = None
    is_active: bool = True
    is_staff: bool = False
    is_superuser: bool = False
    first_name: str = ""
    last_name: str = ""


# Схема для создания пользователя через API
class UserCreate(UserBase):
    password: str


# Схема для регистрации пользователя
class UserRegister(SQLModel):
    email: EmailStr
    password: str
    full_name: str | None = None


# Схема для обновления пользователя (все поля опциональны)
class UserUpdate(SQLModel):
    email: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    password: str | None = None


# Схема для обновления собственного профиля
class UserUpdateMe(SQLModel):
    full_name: str | None = None
    email: EmailStr | None = None


# Схема для обновления пароля
class UpdatePassword(SQLModel):
    current_password: str
    new_password: str


# Схема для возврата данных пользователя через API
class UserPublic(UserBase):
    id: UUID


# Схема для списка пользователей
class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Схема для чтения данных пользователя
class UserRead(UserBase):
    id: UUID
