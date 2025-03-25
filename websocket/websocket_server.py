import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from redis.asyncio import Redis
import json
import uuid
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from typing import Any
import os
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем SERVER_ID глобально перед использованием
SERVER_ID = str(uuid.uuid4())
SERVER_URL = f"{os.getenv('WEBSOCKET_URL')}"
SECRET_KEY = os.getenv(
    "SECRET_KEY", "default-secret-key"
)  # Должен быть тот же, что и в основном приложении
ALGORITHM = "HS256"


class TokenPayload(BaseModel):
    sub: str
    exp: int


async def decode_token(token: str) -> dict[str, Any] | None:
    """Декодирует и верифицирует JWT токен"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    logger.info(f"Starting WebSocket server with ID: {SERVER_ID}")
    await register_server()
    task = asyncio.create_task(redis_subscriber())
    session_tracker_task = asyncio.create_task(update_active_sessions())
    yield
    # Shutdown
    task.cancel()
    session_tracker_task.cancel()
    await unregister_server()
    await redis.close()
    logger.info(f"WebSocket server {SERVER_ID} shut down")


app = FastAPI(lifespan=lifespan)
redis = Redis.from_url("redis://redis:6379")


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_metadata: dict[str, dict[str, str]] = {}
        self.user_connections: dict[
            str, list[str]
        ] = {}  # user_id -> list of client_ids
        self.server_id = SERVER_ID

    async def connect(
        self, client_id: str, websocket: WebSocket, user_id: str | None = None
    ):
        await websocket.accept()
        self.active_connections[client_id] = websocket

        # Получаем IP и User-Agent безопасно
        client_host = getattr(websocket.client, "host", "unknown")
        user_agent = websocket.headers.get("user-agent", "Unknown")

        self.connection_metadata[client_id] = {
            "connected_at": datetime.now().isoformat(),
            "server_id": SERVER_ID,
            "last_activity": datetime.now().isoformat(),
            "ip": client_host,
            "user_agent": user_agent,
            "user_id": user_id if user_id else "anonymous",
        }

        # Если пользователь авторизован, добавляем связь user_id -> client_id
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
            self.user_connections[user_id].append(client_id)

        await self.update_session_info(client_id)
        logger.info(
            f"Client {client_id} connected to server {SERVER_ID}"
            + (f" for user {user_id}" if user_id else "")
        )

    async def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            # Если соединение принадлежало авторизованному пользователю,
            # удаляем его из user_connections
            user_id = self.connection_metadata.get(client_id, {}).get("user_id")
            if user_id and user_id in self.user_connections:
                if client_id in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(client_id)
                # Если это было последнее соединение пользователя, удаляем запись
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]

            del self.active_connections[client_id]
            if client_id in self.connection_metadata:
                await redis.hdel("websocket_sessions", client_id)  # type: ignore
                del self.connection_metadata[client_id]
            logger.info(f"Client {client_id} disconnected from server {SERVER_ID}")

    async def send_to_client(self, client_id: str, message: str) -> bool:
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)
            # Обновляем время последней активности
            if client_id in self.connection_metadata:
                self.connection_metadata[client_id]["last_activity"] = (
                    datetime.now().isoformat()
                )
                await self.update_session_info(client_id)
            return True
        return False

    async def send_to_user(self, user_id: str, message: str) -> list[str]:
        """Отправляет сообщение всем соединениям пользователя на этом сервере"""
        sent_to_clients = []
        if user_id in self.user_connections:
            for client_id in self.user_connections[user_id]:
                if await self.send_to_client(client_id, message):
                    sent_to_clients.append(client_id)
        return sent_to_clients

    async def update_session_info(self, client_id: str) -> None:
        """Обновляет информацию о сессии в Redis"""
        if client_id in self.connection_metadata:
            await redis.hset(
                "websocket_sessions",
                client_id,
                json.dumps(self.connection_metadata[client_id]),
            )  # type: ignore

    def get_all_sessions(self) -> dict[str, Any]:
        """Возвращает количество активных соединений на этом сервере"""
        return {
            "server_id": SERVER_ID,
            "active_connections": len(self.active_connections),
            "authorized_users": len(self.user_connections),
            "clients": list(self.active_connections.keys()),
        }


manager = ConnectionManager()


async def register_server() -> bool:
    """Регистрирует этот сервер в Redis"""
    server_info = {
        "id": SERVER_ID,
        "url": SERVER_URL,
        "started_at": datetime.now().isoformat(),
        "active_connections": 0,
    }
    await redis.hset("active_websocket_servers", SERVER_ID, json.dumps(server_info))  # type: ignore
    logger.info(f"Registered WebSocket server: {SERVER_ID}")
    return True


async def unregister_server() -> int:
    """Удаляет этот сервер из Redis"""
    result = await redis.hdel("active_websocket_servers", SERVER_ID)  # type: ignore
    # Удаляем все сессии, связанные с этим сервером
    all_sessions = await redis.hgetall("websocket_sessions")  # type: ignore
    for client_id, session_data in all_sessions.items():
        try:
            decoded_data = (
                session_data.decode("utf-8")
                if isinstance(session_data, bytes)
                else session_data
            )
            session = json.loads(decoded_data)
            if session.get("server_id") == SERVER_ID:
                await redis.hdel("websocket_sessions", client_id)  # type: ignore
        except Exception as e:
            logger.error(f"Error processing session: {e}")
            continue
    logger.info(f"Unregistered WebSocket server: {SERVER_ID}")
    return result


async def update_active_sessions() -> None:
    """Периодически обновляет информацию о сервере и активных сессиях"""
    while True:
        try:
            server_info = {
                "id": SERVER_ID,
                "url": SERVER_URL,
                "updated_at": datetime.now().isoformat(),
                "active_connections": len(manager.active_connections),
                "authorized_users": len(manager.user_connections),
            }
            await redis.hset(
                "active_websocket_servers", SERVER_ID, json.dumps(server_info)
            )  # type: ignore

            # Каждые 30 секунд
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error updating sessions: {e}")
            await asyncio.sleep(5)


async def redis_subscriber() -> None:
    """Слушаем ответы от основного приложения"""
    pubsub = redis.pubsub()
    await pubsub.subscribe("websocket_responses")
    await pubsub.subscribe(f"websocket_server_{SERVER_ID}")

    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                # В асинхронном Redis данные приходят в bytes
                data_bytes = message["data"]
                if isinstance(data_bytes, bytes):
                    data = json.loads(data_bytes.decode())
                    client_id = data.get("client_id")
                    user_id = data.get("user_id")
                    response = data.get("response")

                    # Если сообщение для конкретного пользователя
                    if user_id:
                        clients_sent = await manager.send_to_user(
                            user_id, json.dumps(response)
                        )
                        if not clients_sent and data.get("broadcast_if_missing", False):
                            # Пользователь не найден на этом сервере - оповестим другие серверы
                            await redis.publish(
                                "websocket_user_lookup",
                                json.dumps(
                                    {
                                        "user_id": user_id,
                                        "original_server_id": SERVER_ID,
                                        "response": response,
                                    }
                                ),
                            )
                    # Если сообщение для конкретного клиента
                    elif client_id:
                        success = await manager.send_to_client(
                            client_id, json.dumps(response)
                        )
                        if not success and data.get("broadcast_if_missing", False):
                            # Клиент не найден на этом сервере - оповестим другие серверы
                            await redis.publish(
                                "websocket_client_lookup",
                                json.dumps(
                                    {
                                        "client_id": client_id,
                                        "original_server_id": SERVER_ID,
                                        "response": response,
                                    }
                                ),
                            )
                    # Если это команда для сервера
                    elif data.get("command") == "get_status":
                        # Отправляем статус сервера
                        server_status = manager.get_all_sessions()
                        await redis.publish(
                            data.get("reply_channel", "websocket_server_status"),
                            json.dumps(
                                {"server_id": SERVER_ID, "status": server_status}
                            ),
                        )
            except (json.JSONDecodeError, AttributeError) as e:
                logger.error(f"Error processing message: {e}")
                continue


@app.websocket("/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket, client_id: str, token: str | None = Query(None)
):
    user_id = None

    # Если есть токен, проверяем его
    if token:
        payload = await decode_token(token)
        if payload:
            user_id = payload.get("sub")
            # Записываем информацию о юзере в логи
            logger.info(f"Authenticated connection for user {user_id}")

    # Принимаем соединение в любом случае, но с информацией о пользователе, если он авторизован
    await manager.connect(client_id, websocket, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            # Отправляем событие в Redis для обработки основным приложением
            event_data = {
                "client_id": client_id,
                "event": data,
                "server_id": SERVER_ID,
                "timestamp": datetime.now().isoformat(),
            }

            # Добавляем информацию о пользователе, если он авторизован
            if user_id:
                event_data["user_id"] = user_id

            await redis.publish("websocket_events", json.dumps(event_data))
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
        # Уведомляем основное приложение об отключении клиента
        disconnect_data = {
            "client_id": client_id,
            "event_type": "disconnect",
            "server_id": SERVER_ID,
            "timestamp": datetime.now().isoformat(),
        }

        # Добавляем информацию о пользователе, если он был авторизован
        if user_id:
            disconnect_data["user_id"] = user_id

        await redis.publish("websocket_events", json.dumps(disconnect_data))


@app.get("/health")
async def health_check():
    """Эндпоинт для проверки здоровья сервиса"""
    return {
        "status": "healthy",
        "server_id": SERVER_ID,
        "active_connections": len(manager.active_connections),
        "authorized_users": len(manager.user_connections),
    }
