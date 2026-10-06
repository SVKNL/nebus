"""Точка входа FastAPI: HTTP API + фоновый outbox publisher."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.v1 import api_v1_router
from app.config import get_settings
from app.messaging.broker import get_broker
from app.services.outbox import OutboxPublisher

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Базовая конфигурация логов процесса API."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Старт брокера и цикл outbox; корректная остановка при shutdown."""
    setup_logging()
    broker = get_broker()
    await broker.start()
    stop_event = asyncio.Event()
    publisher = OutboxPublisher()
    task = asyncio.create_task(publisher.run_forever(stop_event), name="outbox-publisher")
    logger.info("API started, outbox publisher is running")
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await broker.stop()
        logger.info("API stopped")


def create_app(*, with_lifespan: bool = True) -> FastAPI:
    """Фабрика приложения: в тестах lifespan (брокер/outbox) отключаем."""
    application = FastAPI(
        title="Payment Processing Service",
        description=(
            "Асинхронный микросервис приёма платежей: Outbox → RabbitMQ → consumer, "
            "эмуляция шлюза и webhook с retry/DLQ."
        ),
        version="1.0.0",
        lifespan=lifespan if with_lifespan else None,
    )
    application.include_router(api_v1_router)

    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """Liveness для Docker healthcheck. Без API-ключа, чтобы оркестратор мог стучаться."""
        return {"status": "ok"}

    return application


app = create_app()
