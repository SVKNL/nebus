"""Куда деть сообщение после ошибки обработки: delayed retry или DLQ."""

from __future__ import annotations

import logging

from faststream.rabbit import RabbitBroker

from app.messaging.retry import ATTEMPT_HEADER, retry_delay_seconds, should_dead_letter
from app.messaging.topology import (
    PAYMENTS_DLQ_ROUTING_KEY,
    PAYMENTS_RETRY_ROUTING_KEY,
    dead_letter_exchange,
    payments_exchange,
)
from app.schemas.events import PaymentNewEvent

logger = logging.getLogger(__name__)


class MessageRouter:
    """Публикует повтор или финальный отказ. Исходное сообщение хендлер подтверждает сам."""

    def __init__(self, broker: RabbitBroker) -> None:
        self._broker = broker

    async def retry_or_dead_letter(self, event: PaymentNewEvent, attempt: int) -> None:
        """attempt — сколько попыток уже было (0 = первая неудача)."""
        if should_dead_letter(attempt):
            await self.dead_letter(event, attempt)
            return

        delay = retry_delay_seconds(attempt)
        next_attempt = attempt + 1
        await self._broker.publish(
            event.model_dump(mode="json"),
            exchange=payments_exchange,
            routing_key=PAYMENTS_RETRY_ROUTING_KEY,
            persist=True,
            headers={ATTEMPT_HEADER: next_attempt},
            expiration=delay,
        )
        logger.warning(
            "Scheduled retry payment_id=%s next_attempt=%s delay_s=%s",
            event.payment_id,
            next_attempt,
            delay,
        )

    async def dead_letter(self, event: PaymentNewEvent, attempt: int) -> None:
        """Окончательный отказ: очередь payments.new.dlq."""
        await self._broker.publish(
            event.model_dump(mode="json"),
            exchange=dead_letter_exchange,
            routing_key=PAYMENTS_DLQ_ROUTING_KEY,
            persist=True,
            headers={ATTEMPT_HEADER: attempt + 1},
        )
        logger.error(
            "Moved to DLQ payment_id=%s attempts=%s",
            event.payment_id,
            attempt + 1,
        )
