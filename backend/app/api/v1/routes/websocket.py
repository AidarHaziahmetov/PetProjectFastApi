from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis

from app.api.v1.deps import get_current_active_superuser, get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.websockets.handlers import broadcast_message as ws_broadcast_message
from app.websockets.handlers import (
    get_all_active_sessions,
    get_all_active_websocket_servers,
    get_session_by_client_id,
    get_websocket_servers_status,
    send_message_to_client,
    user_states,
)

router = APIRouter(tags=["websocket"])
redis = Redis.from_url(settings.REDIS_URL)


class MessageData(BaseModel):
    """Модель данных для отправки сообщений"""

    type: str
    content: dict[str, Any]


class BroadcastData(BaseModel):
    """Модель данных для массовой рассылки"""

    message: MessageData
    exclude_clients: list[str] | None = None


@router.get("/websocket/servers")
async def get_websocket_servers(_: User = Depends(get_current_active_user)):
    """Получить список доступных WebSocket серверов"""
    servers = await get_all_active_websocket_servers()
    return {"servers": servers, "count": len(servers)}


@router.get("/websocket/sessions")
async def get_websocket_sessions(_: User = Depends(get_current_active_superuser)):
    """Получить информацию о всех активных WebSocket сессиях"""
    sessions = await get_all_active_sessions()
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/websocket/sessions/{client_id}")
async def get_client_session(
    client_id: str, _: User = Depends(get_current_active_user)
):
    """Получить информацию о конкретной WebSocket сессии"""
    session = await get_session_by_client_id(client_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сессия не найдена"
        )

    # Добавляем статус пользователя, если он есть
    session["user_state"] = user_states.get(client_id)

    return session


@router.post("/websocket/send/{client_id}")
async def send_message(
    client_id: str, message: MessageData, user: User = Depends(get_current_active_user)
):
    """Отправить сообщение конкретному клиенту"""
    session = await get_session_by_client_id(client_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден"
        )

    success = await send_message_to_client(
        client_id=client_id,
        message={
            "type": message.type,
            "content": message.content,
            "sender": {
                "id": user.id,
                "email": user.email,
                "is_superuser": user.is_superuser,
            },
        },
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось отправить сообщение",
        )

    return {"status": "success"}


@router.post("/websocket/broadcast")
async def broadcast_message(
    data: BroadcastData, user: User = Depends(get_current_active_user)
):
    """Отправить сообщение всем подключенным клиентам"""
    success = await ws_broadcast_message(
        message={
            "type": data.message.type,
            "content": data.message.content,
            "sender": {
                "id": user.id,
                "email": user.email,
                "is_superuser": user.is_superuser,
            },
        },
        exclude_clients=data.exclude_clients,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось отправить сообщение",
        )

    return {"status": "success"}


@router.get("/websocket/servers/status")
async def get_servers_status(_: User = Depends(get_current_active_superuser)):
    """Получить статус всех WebSocket серверов с активными соединениями"""
    status_data = await get_websocket_servers_status()
    return {"status": status_data}


@router.get("/websocket/user-states")
async def get_user_states(_: User = Depends(get_current_active_user)):
    """Получить все пользовательские состояния"""
    return {"user_states": user_states}
