from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

# if TYPE_CHECKING:
#     from .appeal import Appeal
#     from .comment import Comment
#     from .representative import Representative
#     from .specialist import Specialist
#     from .task import Task


# Модель базы данных
class User(SQLModel, table=True):  # или SQLModel вместо LoggableModel
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    first_name: str = Field(max_length=255, default="")
    last_name: str = Field(max_length=255, default="")
    full_name: str | None = None
    is_active: bool = Field(default=True)
    is_staff: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    hashed_password: str

    # Relationships
    # tasks: list["Task"] = Relationship(
    #     back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    # )
    # appeals: list["Appeal"] = Relationship(
    #     back_populates="user",
    #     sa_relationship_kwargs={
    #         "lazy": "selectin",
    #         "primaryjoin": "and_(Appeal.user_id == User.id, Appeal.responsible_user_id != User.id)",
    #     },
    # )
    # responsible_appeals: list["Appeal"] = Relationship(
    #     back_populates="responsible_user",
    #     sa_relationship_kwargs={
    #         "lazy": "selectin",
    #         "primaryjoin": "and_(Appeal.responsible_user_id == User.id, Appeal.user_id != User.id)",
    #     },
    # )
    # specialist: "Specialist" = Relationship(
    #     back_populates="user", sa_relationship_kwargs={"lazy": "selectin"}
    # )
    # representative: Optional["Representative"] = Relationship(back_populates="user")
    # comments: list["Comment"] = Relationship(back_populates="user")

