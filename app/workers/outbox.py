"""Relay таблицы outbox в RabbitMQ.

Крутится в процессе API. Несколько реплик безопасны: строки берутся
через FOR UPDATE SKIP LOCKED.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import (
    OUTBOX_BATCH_SIZE,
    OUTBOX_MAX_PUBLISH_ATTEMPTS,
    OUTBOX_RETENTION_HOURS,
)
from app.db.session import get_session_factory
from app.domain.clock import utc_now
from app.messaging.broker import get_broker
from app.messaging.topology import PAYMENTS_NEW_ROUTING_KEY, payments_exchange
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Неопубликованные строки outbox -> exchange payments."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._broker = get_broker()

    async def publish_batch(self, session: AsyncSession) -> int:
        """Публикует пачку. Возвращает число успешных отправок."""
        published = 0
        now = utc_now()
        async with session.begin():
            stmt = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.published_at.is_(None),
                    OutboxEvent.publish_attempts < OUTBOX_MAX_PUBLISH_ATTEMPTS,
                )
                .order_by(OutboxEvent.created_at)
                .limit(OUTBOX_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            events = list(await session.scalars(stmt))
            for event in events:
                try:
                    await self._broker.publish(
                        event.payload,
                        exchange=payments_exchange,
                        routing_key=PAYMENTS_NEW_ROUTING_KEY,
                        persist=True,
                    )
                except Exception as exc:
                    event.mark_failed(str(exc))
                    logger.exception("Outbox publish failed id=%s", event.id)
                else:
                    event.mark_published(now)
                    published += 1
                    logger.info(
                        "Outbox published id=%s payment_id=%s type=%s",
                        event.id,
                        event.payment_id,
                        event.event_type,
                    )
        return published

    async def purge_published(self, session: AsyncSession) -> int:
        """Удаляет уже отправленные события старше срока хранения."""
        cutoff = utc_now() - timedelta(hours=OUTBOX_RETENTION_HOURS)
        result = await session.execute(
            delete(OutboxEvent).where(
                OutboxEvent.published_at.is_not(None),
                OutboxEvent.published_at < cutoff,
            )
        )
        await session.commit()
        removed = result.rowcount or 0
        if removed:
            logger.info("Purged %s published outbox rows", removed)
        return removed

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Цикл до сигнала остановки из lifespan FastAPI."""
        interval = self._settings.outbox_poll_interval_seconds
        while not stop_event.is_set():
            try:
                factory = get_session_factory()
                async with factory() as session:
                    await self.publish_batch(session)
                async with factory() as session:
                    await self.purge_published(session)
            except Exception:
                logger.exception("Outbox poll iteration failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except TimeoutError:
                continue
