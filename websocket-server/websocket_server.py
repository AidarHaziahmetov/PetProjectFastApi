import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
import json
import uuid
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await register_server()
    task = asyncio.create_task(redis_subscriber())
    yield
    # Shutdown
    task.cancel()
    await unregister_server()
    await redis.close()


app = FastAPI(lifespan=lifespan)
redis = Redis.from_url("redis://redis:6379")

SERVER_ID = str(uuid.uuid4())
SERVER_URL = f"ws://websocket:{8000}"


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.server_id = SERVER_ID

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    async def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_to_client(self, client_id: str, message: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)


manager = ConnectionManager()


async def register_server():
    await redis.sadd("active_websocket_servers", SERVER_URL)


async def unregister_server():
    await redis.srem("active_websocket_servers", SERVER_URL)


async def redis_subscriber():
    """Слушаем ответы от основного приложения"""
    pubsub = redis.pubsub()
    await pubsub.subscribe("websocket_responses")

    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                # В асинхронном Redis данные приходят в bytes
                data = json.loads(message["data"].decode())
                client_id = data.get("client_id")
                response = data.get("response")
                await manager.send_to_client(client_id, json.dumps(response))
            except (json.JSONDecodeError, AttributeError):
                continue


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Отправляем событие в Redis для обработки основным приложением
            await redis.publish(
                "websocket_events",
                json.dumps(
                    {"client_id": client_id, "event": data, "server_id": SERVER_ID}
                ),
            )
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
        # Уведомляем основное приложение об отключении клиента
        await redis.publish(
            "websocket_events",
            json.dumps(
                {
                    "client_id": client_id,
                    "event_type": "disconnect",
                    "server_id": SERVER_ID,
                }
            ),
        )
