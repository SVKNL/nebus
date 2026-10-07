"""Точка входа FastAPI: HTTP API и фоновый relay outbox."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.errors import register_exception_handlers
from app.api.v1 import api_v1_router
from app.log_config import setup_logging
from app.ops.readiness import readiness_report
from app.workers.broker_loop import supervise_broker


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """HTTP поднимается сразу. Брокер подключается в фоне и не блокирует старт."""
    setup_logging()
    stop_event = asyncio.Event()
    task = asyncio.create_task(supervise_broker(stop_event), name="broker-supervisor")
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def create_app(*, with_lifespan: bool = True) -> FastAPI:
    """В тестах lifespan выключаем: брокер и БД не нужны."""
    application = FastAPI(
        title="Payment Processing Service",
        description=(
            "Приём платежей: запись в БД вместе с outbox, публикация в RabbitMQ, "
            "обработка consumer'ом и webhook."
        ),
        version="1.0.0",
        lifespan=lifespan if with_lifespan else None,
    )
    register_exception_handlers(application)
    application.include_router(api_v1_router)

    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """Liveness: процесс жив. Не проверяет базу и брокер."""
        return {"status": "ok"}

    @application.get("/ready", tags=["ops"])
    async def ready() -> JSONResponse:
        """Readiness: без базы 503. Без брокера сервис degraded, но платежи принимает."""
        report = await readiness_report()
        code = 200 if report["database"] else 503
        return JSONResponse(status_code=code, content=report)

    return application


app = create_app()
