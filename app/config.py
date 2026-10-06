"""Конфигурация сервиса из переменных окружения."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Параметры запуска API, consumer и outbox-publisher.

    Все секреты и адреса инфраструктуры читаются из окружения / файла `.env`,
    чтобы один и тот же образ работал локально и в docker-compose.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(min_length=8, description="Статический ключ заголовка X-API-Key")
    database_url: str = Field(
        min_length=10,
        description="SQLAlchemy URL, например postgresql+asyncpg://user:pass@host:5432/db",
    )
    rabbitmq_url: str = Field(
        min_length=10,
        description="AMQP URL, например amqp://guest:guest@rabbitmq:5672/",
    )
    outbox_poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    webhook_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    log_level: str = Field(default="INFO")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Приводим уровень логирования к верхнему регистру для logging."""
        normalized = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            msg = f"Недопустимый LOG_LEVEL: {value}"
            raise ValueError(msg)
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Кэшируем настройки: процесс читает окружение один раз."""
    return Settings()
