"""FastStream: один обработчик очереди payments.new."""

from __future__ import annotations

import logging

from faststream import FastStream
from faststream.rabbit import RabbitMessage

from app.db.session import get_session_factory
from app.domain.errors import NonRetryableError
from app.log_config import setup_logging
from app.messaging.broker import get_broker
from app.messaging.retry import parse_attempt
from app.messaging.router import MessageRouter
from app.messaging.topology import declare_topology, payments_exchange, payments_new_queue
from app.schemas.events import PaymentNewEvent
from app.services.processor import process_payment_message

logger = logging.getLogger(__name__)

setup_logging()
broker = get_broker()
app = FastStream(broker)
router = MessageRouter(broker)


@app.after_startup
async def _declare_topology() -> None:
    """После connect: retry и DLQ, которые subscriber сам не создаёт."""
    await declare_topology(broker)


@broker.subscriber(payments_new_queue, payments_exchange)
async def handle_payment_new(event: PaymentNewEvent, message: RabbitMessage) -> None:
    """Успех — ack. Ошибка — отложенный retry, после 3-й попытки — DLQ.

    Сообщение подтверждаем сами (хендлер не бросает исключение),
    чтобы брокер не зациклил очередь мгновенным nack.
    """
    attempt = parse_attempt(message.headers)
    logger.info("Received payments.new payment_id=%s attempt=%s", event.payment_id, attempt)
    factory = get_session_factory()
    try:
        async with factory() as session:
            await process_payment_message(session, event.payment_id)
    except NonRetryableError:
        logger.exception("Non-retryable failure payment_id=%s", event.payment_id)
        await router.dead_letter(event, attempt)
        return
    except Exception:
        logger.exception(
            "Payment handling failed payment_id=%s attempt=%s",
            event.payment_id,
            attempt,
        )
        await router.retry_or_dead_letter(event, attempt)
        return
    logger.info("Payment handling succeeded payment_id=%s", event.payment_id)
