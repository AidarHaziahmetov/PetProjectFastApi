import io
import logging
import os
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError

    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("Boto3 library not installed. S3 storage will not be available.")


class FileStorage(Protocol):
    """Протокол для хранилища файлов"""

    async def save_file(self, file_content: BinaryIO | bytes, file_path: str) -> str:
        """Сохраняет файл и возвращает URL или путь к нему"""
        pass

    async def get_file(self, file_path: str) -> bytes | None:
        """Получает содержимое файла по пути или URL"""
        pass

    async def delete_file(self, file_path: str) -> bool:
        """Удаляет файл и возвращает успех операции"""
        pass

    def get_file_url(self, file_path: str) -> str:
        """Возвращает URL для доступа к файлу"""
        pass


class LocalFileStorage(FileStorage):
    """Реализация хранилища файлов на локальной файловой системе"""

    def __init__(self, base_path: str = settings.LOCAL_STORAGE_PATH):
        self.base_path = Path(base_path)
        # Создаем директорию, если она не существует
        os.makedirs(self.base_path, exist_ok=True)

    async def save_file(self, file_content: BinaryIO | bytes, file_path: str) -> str:
        """Сохраняет файл локально и возвращает путь к нему"""
        full_path = self.base_path / file_path

        # Создаем директории, если они не существуют
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Записываем содержимое файла
        mode = "wb"
        if isinstance(file_content, bytes):
            with open(full_path, mode) as file:
                file.write(file_content)
        else:
            with open(full_path, mode) as file:
                file.write(file_content.read())

        return str(file_path)

    async def get_file(self, file_path: str) -> bytes | None:
        """Получает содержимое файла по пути"""
        full_path = self.base_path / file_path
        try:
            with open(full_path, "rb") as file:
                return file.read()
        except FileNotFoundError:
            logger.error(f"Файл не найден: {full_path}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при чтении файла {full_path}: {e}")
            return None

    async def delete_file(self, file_path: str) -> bool:
        """Удаляет файл и возвращает успех операции"""
        full_path = self.base_path / file_path
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                # Удаляем пустые директории
                self._remove_empty_dirs(os.path.dirname(full_path))
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {full_path}: {e}")
            return False

    def _remove_empty_dirs(self, path: str) -> None:
        """Рекурсивно удаляет пустые директории"""
        if path == str(self.base_path):
            return

        try:
            if os.path.isdir(path) and not os.listdir(path):
                os.rmdir(path)
                self._remove_empty_dirs(os.path.dirname(path))
        except Exception as e:
            logger.error(f"Ошибка при удалении директории {path}: {e}")

    def get_file_url(self, file_path: str) -> str:
        """Возвращает URL для доступа к файлу"""
        # В случае локального хранилища возвращаем относительный путь
        # Предполагается, что будет настроен статический маршрут для доступа к файлам
        return f"/static/{file_path}"


class S3FileStorage(FileStorage):
    """Реализация хранилища файлов на S3"""

    def __init__(
        self,
        endpoint_url: str = settings.S3_ENDPOINT_URL,
        access_key: str = settings.S3_ACCESS_KEY,
        secret_key: str = settings.S3_SECRET_KEY,
        bucket_name: str = settings.S3_BUCKET_NAME,
        region: str | None = settings.S3_REGION,
    ):
        if not S3_AVAILABLE:
            raise ImportError(
                "Boto3 library not installed. S3 storage is not available."
            )

        self.endpoint_url = endpoint_url
        self.bucket_name = bucket_name
        self.region = region

        # Инициализируем клиент S3
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    async def save_file(self, file_content: BinaryIO | bytes, file_path: str) -> str:
        """Сохраняет файл в S3 и возвращает путь к нему"""
        try:
            if isinstance(file_content, bytes):
                self.s3_client.upload_fileobj(
                    io.BytesIO(file_content), self.bucket_name, file_path
                )
            else:
                self.s3_client.upload_fileobj(file_content, self.bucket_name, file_path)
            return file_path
        except ClientError as e:
            logger.error(f"Ошибка при загрузке файла в S3: {e}")
            raise

    async def get_file(self, file_path: str) -> bytes | None:
        """Получает содержимое файла из S3"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Ошибка при получении файла из S3: {e}")
            return None

    async def delete_file(self, file_path: str) -> bool:
        """Удаляет файл из S3 и возвращает успех операции"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError as e:
            logger.error(f"Ошибка при удалении файла из S3: {e}")
            return False

    def get_file_url(self, file_path: str) -> str:
        """Возвращает URL для доступа к файлу"""
        # Для публичных бакетов можно использовать прямую ссылку
        if self.endpoint_url:
            return f"{self.endpoint_url}/{self.bucket_name}/{file_path}"

        # Для AWS S3, если endpoint_url не указан
        region_part = f"-{self.region}" if self.region else ""
        return f"https://{self.bucket_name}.s3{region_part}.amazonaws.com/{file_path}"


class StorageFactory:
    """Фабрика для создания хранилища файлов в зависимости от настроек"""

    @staticmethod
    def get_storage() -> FileStorage:
        """Возвращает экземпляр хранилища файлов в зависимости от настроек"""
        if settings.s3_enabled and S3_AVAILABLE:
            try:
                return S3FileStorage()
            except Exception as e:
                logger.error(f"Ошибка при инициализации S3 хранилища: {e}")
                logger.warning("Переключение на локальное хранилище...")
                return LocalFileStorage()
        return LocalFileStorage()


# Функции-хелперы для удобства использования


def get_storage() -> FileStorage:
    """Возвращает экземпляр хранилища файлов"""
    return StorageFactory.get_storage()


def generate_unique_filename(original_filename: str) -> str:
    """Генерирует уникальное имя файла, сохраняя расширение оригинального файла"""
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4()}{ext}"


async def save_uploaded_file(
    file_content: BinaryIO | bytes, directory: str, filename: str
) -> str:
    """Сохраняет загруженный файл в указанную директорию с указанным именем"""
    storage = get_storage()
    file_path = os.path.join(directory, filename)
    return await storage.save_file(file_content, file_path)
