import asyncio
import json
import logging
import uuid
from typing import Any, Protocol

from redis.asyncio import Redis

from app.core.config import settings

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    def __init__(self) -> None:
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


# ----- Дополнительные функции для работы с WebSocket сессиями -----


async def get_all_active_websocket_servers() -> list[dict[str, Any]]:
    """Получает список всех активных WebSocket серверов"""
    try:
        servers_data = await redis.hgetall("active_websocket_servers")  # type: ignore
        servers: list[dict[str, Any]] = []

        for _, server_data in servers_data.items():
            try:
                decoded_data = (
                    server_data.decode("utf-8")
                    if isinstance(server_data, bytes)
                    else server_data
                )
                server_info = json.loads(decoded_data)
                servers.append(server_info)
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Ошибка при десериализации данных сервера: {e}")
                continue

        return servers
    except Exception as e:
        logger.error(f"Ошибка при получении списка серверов: {e}")
        return []


async def get_all_active_sessions() -> dict[str, dict[str, Any]]:
    """Получает информацию о всех активных WebSocket сессиях"""
    try:
        sessions_data = await redis.hgetall("websocket_sessions")  # type: ignore
        sessions: dict[str, dict[str, Any]] = {}

        for client_id, session_data in sessions_data.items():
            try:
                client_id_str = (
                    client_id.decode("utf-8")
                    if isinstance(client_id, bytes)
                    else client_id
                )
                decoded_data = (
                    session_data.decode("utf-8")
                    if isinstance(session_data, bytes)
                    else session_data
                )
                session_info = json.loads(decoded_data)
                sessions[client_id_str] = session_info
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Ошибка при десериализации данных сессии: {e}")
                continue

        return sessions
    except Exception as e:
        logger.error(f"Ошибка при получении списка сессий: {e}")
        return {}


async def get_session_by_client_id(client_id: str) -> dict[str, Any] | None:
    """Получает информацию о конкретной WebSocket сессии"""
    try:
        session_data = await redis.hget("websocket_sessions", client_id)  # type: ignore
        if session_data is None:
            return None

        decoded_data = (
            session_data.decode("utf-8")
            if isinstance(session_data, bytes)
            else session_data
        )
        return json.loads(decoded_data)
    except Exception as e:
        logger.error(f"Ошибка при получении информации о сессии {client_id}: {e}")
        return None


async def send_message_to_client(
    client_id: str, message: dict[str, Any], broadcast_if_missing: bool = False
) -> bool:
    """Отправляет сообщение конкретному клиенту через WebSocket"""
    try:
        # Проверяем, есть ли у нас информация о сессии этого клиента
        session_info = await get_session_by_client_id(client_id)

        if session_info:
            # Если знаем, на каком сервере находится клиент, отправляем сообщение напрямую
            server_id = session_info.get("server_id")
            if server_id:
                await redis.publish(
                    f"websocket_server_{server_id}",
                    json.dumps({"client_id": client_id, "response": message}),
                )
                return True

        # Если не знаем точного сервера или хотим разослать всем
        await redis.publish(
            "websocket_responses",
            json.dumps(
                {
                    "client_id": client_id,
                    "response": message,
                    "broadcast_if_missing": broadcast_if_missing,
                }
            ),
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения клиенту {client_id}: {e}")
        return False


async def broadcast_message(
    message: dict[str, Any], exclude_clients: list[str] | None = None
) -> bool:
    """Отправляет сообщение всем подключенным клиентам"""
    try:
        exclude_list: list[str] = exclude_clients if exclude_clients is not None else []

        # Получаем все активные сессии
        sessions = await get_all_active_sessions()

        # Группируем клиентов по серверам для оптимизации отправки
        server_clients: dict[str, list[str]] = {}
        for client_id, session in sessions.items():
            if client_id in exclude_list:
                continue

            server_id = session.get("server_id")
            if server_id:
                if server_id not in server_clients:
                    server_clients[server_id] = []
                server_clients[server_id].append(client_id)

        # Отправляем групповые сообщения для каждого сервера
        for server_id, clients in server_clients.items():
            await redis.publish(
                f"websocket_server_{server_id}",
                json.dumps(
                    {"broadcast": True, "clients": clients, "response": message}
                ),
            )

        # Также отправляем в общий канал для клиентов, которые могли не попасть в группы
        await redis.publish(
            "websocket_responses",
            json.dumps(
                {
                    "broadcast": True,
                    "exclude_clients": exclude_list,
                    "response": message,
                }
            ),
        )

        return True
    except Exception as e:
        logger.error(f"Ошибка при массовой рассылке сообщения: {e}")
        return False


async def get_websocket_servers_status() -> list[dict[str, Any]]:
    """Запрашивает статус у всех WebSocket серверов"""
    try:
        # Получаем список всех серверов
        servers = await get_all_active_websocket_servers()

        # Создаем уникальный канал для ответов
        response_id = str(uuid.uuid4())
        response_channel = f"websocket_status_response_{response_id}"

        # Подписываемся на канал ответов
        pubsub = redis.pubsub()
        await pubsub.subscribe(response_channel)

        # Запрашиваем статус у всех серверов
        for server in servers:
            server_id = server.get("id")
            if server_id:
                await redis.publish(
                    f"websocket_server_{server_id}",
                    json.dumps(
                        {"command": "get_status", "reply_channel": response_channel}
                    ),
                )

        # Собираем ответы в течение определенного времени
        timeout = 2.0  # 2 секунды на сбор ответов
        results: list[dict[str, Any]] = []

        async def collect_responses():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data_bytes = message["data"]
                        if isinstance(data_bytes, bytes):
                            data = json.loads(data_bytes.decode())
                            results.append(data)
                    except Exception as e:
                        logger.error(f"Ошибка при обработке ответа: {e}")

        # Запускаем сбор ответов с таймаутом
        collector_task = asyncio.create_task(collect_responses())
        try:
            await asyncio.wait_for(asyncio.shield(collector_task), timeout=timeout)
        except TimeoutError:
            pass
        finally:
            collector_task.cancel()
            await pubsub.unsubscribe(response_channel)

        return results
    except Exception as e:
        logger.error(f"Ошибка при запросе статуса серверов: {e}")
        return []
