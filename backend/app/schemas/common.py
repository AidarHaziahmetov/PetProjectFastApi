from sqlmodel import SQLModel


class ApiMessage(SQLModel):
    message: str
