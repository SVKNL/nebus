"""Маршрутизация после ошибки: retry с задержкой или сразу DLQ."""

from unittest.mock import AsyncMock
from uuid import uuid4

from app.messaging.router import MessageRouter
from app.schemas.events import PaymentNewEvent


def _event() -> PaymentNewEvent:
    return PaymentNewEvent(payment_id=uuid4())


async def test_first_failure_goes_to_retry() -> None:
    broker = AsyncMock()
    event = _event()
    await MessageRouter(broker).retry_or_dead_letter(event, attempt=0)
    broker.publish.assert_awaited_once()
    kwargs = broker.publish.await_args.kwargs
    assert kwargs["routing_key"] == "payments.retry"
    assert kwargs["expiration"] == 1
    assert kwargs["headers"]["x-attempt"] == 1


async def test_third_failure_goes_to_dlq() -> None:
    broker = AsyncMock()
    event = _event()
    await MessageRouter(broker).retry_or_dead_letter(event, attempt=2)
    kwargs = broker.publish.await_args.kwargs
    assert kwargs["routing_key"] == "payments.new.dlq"
    assert kwargs["headers"]["x-attempt"] == 3
