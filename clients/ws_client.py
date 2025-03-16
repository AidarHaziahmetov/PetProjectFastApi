import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)

async def run_client():
    uri = "ws://localhost:8765"
    reconnect_delay = 3  # начальная задержка перед повторной попыткой
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                logging.info("Подключение установлено к серверу %s", uri)
                # Отправляем приветственное сообщение
                logging.info("Отправляем приветственное сообщение")
                await websocket.send("Привет, сервер!")
                # Постоянное чтение сообщений
                while True:
                    message = await websocket.recv()
                    logging.info("Получено сообщение: %s", message)
        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError) as e:
            logging.error("Соединение потеряно: %s. Пытаемся переподключиться через %s секунд...", e, reconnect_delay)
            await asyncio.sleep(reconnect_delay)
            # При необходимости можно увеличить задержку для экспоненциального бэкафа
        except Exception as e:
            logging.error("Произошла ошибка: %s. Пытаемся переподключиться через %s секунд...", e, reconnect_delay)
            await asyncio.sleep(reconnect_delay)

if __name__ == "__main__":
    asyncio.run(run_client()) 