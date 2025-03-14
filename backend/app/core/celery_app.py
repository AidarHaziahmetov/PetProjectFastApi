from celery import Celery

from app.core.config import settings

# Создаем экземпляр Celery с указанием брокера и бекенда для результатов
celery_app = Celery(
    "backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Настройка маршрутизации задач: все задачи из app.tasks.* отправляются в очередь "default"
celery_app.conf.task_routes = {
    "app.tasks.*": {"queue": "default"},
}
# TODO возможно понадобится celery beat для периодических задач
