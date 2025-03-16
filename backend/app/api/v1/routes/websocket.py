import json

from fastapi import APIRouter
from redis.asyncio import Redis

from app.core.config import settings

router = APIRouter(tags=["websocket"])
redis = Redis.from_url(settings.REDIS_URL)


@router.get("/websocket-servers")
async def get_websocket_servers():
    """Получить список доступных WebSocket серверов"""
    servers = await redis.smembers("active_websocket_servers")

    return {"servers": [server.decode() for server in servers]}


@router.get("/user-status/{client_id}")
async def get_user_status(client_id: str):
    """Получить статус пользователя"""
    from app.websockets.handlers import user_states

    return {"status": user_states.get(client_id)}


@router.post("/broadcast")
async def broadcast_message(message: dict):
    """Отправить сообщение всем подключенным клиентам"""
    await redis.publish(
        "websocket_responses",
        json.dumps(
            {
                "client_id": "broadcast",
                "response": {"type": "broadcast", "message": message},
            }
        ),
    )
    return {"status": "success"}
