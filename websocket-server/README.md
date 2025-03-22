# WebSocket сервер с поддержкой авторизации

Этот WebSocket сервер позволяет устанавливать как анонимные, так и авторизованные соединения с использованием JWT токенов из основного FastAPI приложения.

## Подключение к WebSocket

### Анонимное подключение

Для анонимного подключения используйте URL-адрес:

```
ws://ws.localhost/ws/{client_id}
```

где `{client_id}` - это уникальный идентификатор клиента (может быть любой строкой).

### Авторизованное подключение

Для авторизованного подключения необходимо передать JWT-токен в параметре запроса:

```
ws://ws.localhost/ws/{client_id}?token={jwt_token}
```

где:
- `{client_id}` - уникальный идентификатор клиента
- `{jwt_token}` - действительный JWT-токен, полученный от основного API через эндпоинт `/api/v1/login/access-token`

## Получение JWT-токена

1. Выполните POST-запрос к эндпоинту `/api/v1/login/access-token` с учетными данными пользователя
2. Получите токен из ответа в поле `access_token`
3. Используйте этот токен при установлении WebSocket соединения

## Примеры использования

### JavaScript (браузер)

```javascript
// Получение токена (пример с использованием fetch)
async function getToken() {
  const response = await fetch('https://api.localhost/api/v1/login/access-token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      'username': 'user@example.com',
      'password': 'password123'
    })
  });

  const data = await response.json();
  return data.access_token;
}

// Подключение к WebSocket с авторизацией
async function connectWebSocket() {
  // Генерируем уникальный client_id
  const clientId = Date.now().toString();
  // Получаем токен
  const token = await getToken();

  // Подключаемся к WebSocket с токеном
  const socket = new WebSocket(`ws://ws.localhost/ws/${clientId}?token=${token}`);

  socket.onopen = function(e) {
    console.log("WebSocket соединение установлено");
    socket.send(JSON.stringify({type: "hello", message: "Привет, сервер!"}));
  };

  socket.onmessage = function(event) {
    console.log(`Получено сообщение: ${event.data}`);
  };

  socket.onclose = function(event) {
    if (event.wasClean) {
      console.log(`Соединение закрыто корректно, код=${event.code} причина=${event.reason}`);
    } else {
      console.log('Соединение прервано');
    }
  };

  socket.onerror = function(error) {
    console.log(`Ошибка: ${error.message}`);
  };

  return socket;
}
```

### Python

```python
import asyncio
import websockets
import requests
import json

async def connect_websocket():
    # Получение токена через API
    response = requests.post(
        'https://api.localhost/api/v1/login/access-token',
        data={
            'username': 'user@example.com',
            'password': 'password123'
        }
    )
    token = response.json()['access_token']

    # Подключение к WebSocket с токеном
    client_id = str(asyncio.get_event_loop().time())
    uri = f"ws://ws.localhost/ws/{client_id}?token={token}"

    async with websockets.connect(uri) as websocket:
        print("WebSocket соединение установлено")

        # Отправка сообщения
        await websocket.send(json.dumps({
            "type": "hello",
            "message": "Привет, сервер!"
        }))

        # Получение ответа
        response = await websocket.recv()
        print(f"Получено сообщение: {response}")

asyncio.run(connect_websocket())
```

## Безопасность

- JWT-токены имеют ограниченный срок действия
- Соединения без действительного токена обрабатываются как анонимные
- Информация о пользователе доступна для обработки сообщений на сервере
- Для авторизованных пользователей сохраняется связь между user_id и client_id
