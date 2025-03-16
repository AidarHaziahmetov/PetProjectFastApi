# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "websockets",
# ]
# ///


import asyncio
import websockets
from websockets.exceptions import ConnectionClosedOK
from typing import Any


async def handle_websocket(websocket: Any) -> None:
    try:
        async for message in websocket:
            # Обработка полученного сообщения
            print(f"Received message: {message}")
            # Отправка сообщения обратно клиенту
            await asyncio.sleep(4)
            await websocket.send(f"Server received: {message}")
            print(f"Sent message: {message}")
    except ConnectionClosedOK:
        print(f"WebSocket {websocket.remote_address} connection closed")


async def main() -> None:
    print("Starting websocket server...")
    async with websockets.serve(handle_websocket, "0.0.0.0", 8765):
        print("Websocket server started on ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever


asyncio.run(main())
