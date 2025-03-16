import asyncio
import json
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from redis.asyncio import Redis
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.main import api_router
from app.core.config import settings
from app.websockets.handlers import handle_disconnect, handle_message


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

# Инициализация Redis
redis = Redis.from_url(settings.REDIS_URL)


async def websocket_event_handler():
    """Обработчик событий от WebSocket серверов"""
    pubsub = redis.pubsub()
    await pubsub.subscribe("websocket_events")

    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                data = json.loads(message["data"])
                client_id = data.get("client_id")

                if data.get("event_type") == "disconnect":
                    await handle_disconnect(client_id)
                else:
                    await handle_message(client_id, data.get("event"))
            except json.JSONDecodeError:
                continue


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    task = asyncio.create_task(websocket_event_handler())
    yield
    # Shutdown
    task.cancel()
    await redis.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
