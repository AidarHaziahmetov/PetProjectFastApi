import json
from typing import Any, Protocol

from redis.asyncio import Redis

from app.core.config import settings

# Инициализация Redis
redis = Redis.from_url(settings.REDIS_URL)

# Хранилище состояний пользователей
user_states: dict[str, Any] = {}


class WebSocketHandler(Protocol):
    """Протокол для обработчиков WebSocket событий"""

    async def handle(self, client_id: str, data: dict) -> dict:
        """Обработать событие и вернуть ответ"""
        ...


class ChatMessageHandler:
    async def handle(self, client_id: str, data: dict) -> dict:
        return {
            "type": "chat_response",
            "message": f"Получено сообщение: {data.get('message')}",
        }


class StatusUpdateHandler:
    async def handle(self, client_id: str, data: dict) -> dict:
        user_states[client_id] = data.get("status")
        return {"type": "status_updated", "status": data.get("status")}


class ErrorHandler:
    async def handle(self, client_id: str, data: dict) -> dict:
        return {"type": "error", "message": "Неизвестный тип события"}


class WebSocketMessageRouter:
    def __init__(self):
        self.handlers: dict[str, WebSocketHandler] = {
            "chat_message": ChatMessageHandler(),
            "status_update": StatusUpdateHandler(),
        }
        self.error_handler = ErrorHandler()

    async def route_message(
        self, client_id: str, message_type: str, data: dict
    ) -> dict:
        handler = self.handlers.get(message_type, self.error_handler)
        return await handler.handle(client_id, data)


# Создаем глобальный роутер
message_router = WebSocketMessageRouter()


async def handle_message(client_id: str, message: str):
    """Обработка сообщений от клиента"""
    try:
        data = json.loads(message)
        message_type = data.get("type", "unknown")

        # Получаем ответ от соответствующего обработчика
        response = await message_router.route_message(client_id, message_type, data)

        # Отправляем ответ обратно через Redis
        await redis.publish(
            "websocket_responses",
            json.dumps({"client_id": client_id, "response": response}),
        )

    except json.JSONDecodeError:
        await redis.publish(
            "websocket_responses",
            json.dumps(
                {
                    "client_id": client_id,
                    "response": {"type": "error", "message": "Неверный формат JSON"},
                }
            ),
        )


async def handle_disconnect(client_id: str):
    """Обработка отключения клиента"""
    if client_id in user_states:
        del user_states[client_id]
