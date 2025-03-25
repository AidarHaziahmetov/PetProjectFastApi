from typing import Any, Generic, TypeVar

from sqlalchemy import and_
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

ModelType = TypeVar("ModelType", bound=SQLModel)


class FilterOperator:
    EQ = "eq"  # равно
    NEQ = "neq"  # не равно
    GT = "gt"  # больше
    GTE = "gte"  # больше или равно
    LT = "lt"  # меньше
    LTE = "lte"  # меньше или равно
    IN = "in"  # в списке
    NIN = "nin"  # не в списке
    LIKE = "like"  # LIKE
    ILIKE = "ilike"  # ILIKE (регистронезависимый)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    def _build_filters(self, filters: dict[str, Any]) -> list:
        conditions = []
        for field, value in filters.items():
            if "__" in field:
                field_name, operator = field.split("__")
                if operator == FilterOperator.EQ:
                    conditions.append(getattr(self.model, field_name) == value)
                elif operator == FilterOperator.NEQ:
                    conditions.append(getattr(self.model, field_name) != value)
                elif operator == FilterOperator.GT:
                    conditions.append(getattr(self.model, field_name) > value)
                elif operator == FilterOperator.GTE:
                    conditions.append(getattr(self.model, field_name) >= value)
                elif operator == FilterOperator.LT:
                    conditions.append(getattr(self.model, field_name) < value)
                elif operator == FilterOperator.LTE:
                    conditions.append(getattr(self.model, field_name) <= value)
                elif operator == FilterOperator.IN:
                    conditions.append(getattr(self.model, field_name).in_(value))
                elif operator == FilterOperator.NIN:
                    conditions.append(~getattr(self.model, field_name).in_(value))
                elif operator == FilterOperator.LIKE:
                    conditions.append(getattr(self.model, field_name).like(value))
                elif operator == FilterOperator.ILIKE:
                    conditions.append(getattr(self.model, field_name).ilike(value))
            else:
                conditions.append(getattr(self.model, field) == value)
        return conditions

    async def filter(
        self,
        filters: dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[ModelType]:
        query = select(self.model)

        if filters:
            conditions = self._build_filters(filters)
            query = query.where(and_(*conditions))

        if order_by:
            if order_by.startswith("-"):
                query = query.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                query = query.order_by(getattr(self.model, order_by))

        query = query.offset(skip).limit(limit)
        result = await self.session.exec(query)
        return list(result.all())
