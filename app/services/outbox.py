"""Публикация событий из таблицы outbox в RabbitMQ.

Publisher крутится фоном в процессе API: так в compose достаточно сервисов
api + consumer, без отдельного «relay». Несколько реплик API безопасны —
строки берутся через FOR UPDATE SKIP LOCKED.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import OUTBOX_BATCH_SIZE, PAYMENTS_NEW_ROUTING_KEY
from app.db.session import get_session_factory
from app.messaging.broker import get_broker
from app.messaging.queues import payments_exchange
from app.models.outbox import OutboxEvent

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Relay: неопубликованные строки outbox → exchange payments."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._broker = get_broker()

    async def publish_batch(self, session: AsyncSession) -> int:
        """Публикует пачку событий. Возвращает число успешно отправленных."""
        published = 0
        now = datetime.now(UTC)
        async with session.begin():
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.created_at)
                .limit(OUTBOX_BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )
            result = await session.scalars(stmt)
            events = list(result)
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

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Цикл до сигнала остановки (lifespan FastAPI)."""
        interval = self._settings.outbox_poll_interval_seconds
        while not stop_event.is_set():
            try:
                factory = get_session_factory()
                async with factory() as session:
                    await self.publish_batch(session)
            except Exception:
                logger.exception("Outbox poll iteration failed")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except TimeoutError:
                continue
