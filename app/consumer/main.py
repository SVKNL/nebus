"""FastStream consumer: один обработчик очереди payments.new."""

from __future__ import annotations

import logging

from faststream import FastStream
from faststream.rabbit import RabbitMessage

from app.config import get_settings
from app.constants import (
    PAYMENTS_DLQ_ROUTING_KEY,
    PAYMENTS_RETRY_ROUTING_KEY,
)
from app.db.session import get_session_factory
from app.messaging.broker import get_broker
from app.messaging.queues import (
    dead_letter_exchange,
    payments_exchange,
    payments_new_queue,
)
from app.messaging.retry import (
    ATTEMPT_HEADER,
    parse_attempt,
    retry_delay_seconds,
    should_dead_letter,
)
from app.schemas.payment import PaymentNewEvent
from app.services.processor import process_payment_message

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Логи процесса consumer."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


setup_logging()
broker = get_broker()
app = FastStream(broker)


@broker.subscriber(payments_new_queue, payments_exchange)
async def handle_payment_new(event: PaymentNewEvent, message: RabbitMessage) -> None:
    """Единственный consumer по ТЗ.

    Успех → ack (FastStream сделает сам, если хендлер не бросил исключение).
    Ошибка → не nack в бесконечный requeue, а:
      * публикация в payments.retry с TTL (экспоненциальная задержка), либо
      * публикация в DLQ после 3-й неудачи.
    Текущее сообщение при этом подтверждается, чтобы не зациклить очередь.
    """
    attempt = parse_attempt(message.headers)
    logger.info(
        "Received payments.new payment_id=%s attempt=%s",
        event.payment_id,
        attempt,
    )
    factory = get_session_factory()
    try:
        async with factory() as session:
            await process_payment_message(session, event.payment_id)
    except Exception:
        logger.exception(
            "Payment handling failed payment_id=%s attempt=%s",
            event.payment_id,
            attempt,
        )
        await _retry_or_dead_letter(event, attempt)
        return
    logger.info("Payment handling succeeded payment_id=%s", event.payment_id)


async def _retry_or_dead_letter(event: PaymentNewEvent, attempt: int) -> None:
    """Маршрутизация после сбоя обработки: delayed retry либо DLQ."""
    payload = event.model_dump(mode="json")
    if should_dead_letter(attempt):
        await broker.publish(
            payload,
            exchange=dead_letter_exchange,
            routing_key=PAYMENTS_DLQ_ROUTING_KEY,
            persist=True,
            headers={ATTEMPT_HEADER: attempt + 1},
        )
        logger.error(
            "Message moved to DLQ payment_id=%s after %s attempts",
            event.payment_id,
            attempt + 1,
        )
        return

    delay = retry_delay_seconds(attempt)
    next_attempt = attempt + 1
    # FastStream: expiration — время жизни сообщения в секундах (не миллисекундах).
    await broker.publish(
        payload,
        exchange=payments_exchange,
        routing_key=PAYMENTS_RETRY_ROUTING_KEY,
        persist=True,
        headers={ATTEMPT_HEADER: next_attempt},
        expiration=delay,
    )
    logger.warning(
        "Message scheduled for retry payment_id=%s next_attempt=%s delay_s=%s",
        event.payment_id,
        next_attempt,
        delay,
    )
