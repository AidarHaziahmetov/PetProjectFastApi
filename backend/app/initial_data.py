import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.init_db import init_db
from app.db.session import async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init() -> None:
    async with AsyncSession(async_engine) as session:
        await init_db(session)


def main() -> None:
    logger.info("Creating initial data")
    asyncio.run(init())
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
