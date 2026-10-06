"""Идемпотентный процессор: шлюз только для pending, webhook — если ещё не уходил."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from app.models.payment import Payment, PaymentStatus
from app.services.processor import PaymentProcessor


class _FakeGateway:
    def __init__(self) -> None:
        self.calls = 0

    async def charge(self, payment: Payment) -> PaymentStatus:
        self.calls += 1
        _ = payment
        return PaymentStatus.SUCCEEDED


class _FakeNotifier:
    def __init__(self) -> None:
        self.calls = 0

    async def notify(self, payment: Payment) -> None:
        self.calls += 1
        payment.webhook_sent_at = datetime.now(UTC)


async def test_process_pending_charges_and_notifies(payment: Payment) -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=payment)
    session.commit = AsyncMock()
    gateway = _FakeGateway()
    notifier = _FakeNotifier()

    processor = PaymentProcessor(session, gateway=gateway, notifier=notifier)
    await processor.process(payment.id)

    assert gateway.calls == 1
    assert notifier.calls == 1
    assert payment.status is PaymentStatus.SUCCEEDED
    assert session.commit.await_count == 2


async def test_process_skips_gateway_if_terminal(payment: Payment) -> None:
    payment.status = PaymentStatus.FAILED
    payment.processed_at = datetime.now(UTC)
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=payment)
    session.commit = AsyncMock()
    gateway = _FakeGateway()
    notifier = _FakeNotifier()

    processor = PaymentProcessor(session, gateway=gateway, notifier=notifier)
    await processor.process(payment.id)

    assert gateway.calls == 0
    assert notifier.calls == 1


async def test_process_skips_webhook_if_already_sent(payment: Payment) -> None:
    payment.status = PaymentStatus.SUCCEEDED
    payment.webhook_sent_at = datetime.now(UTC)
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=payment)
    gateway = _FakeGateway()
    notifier = _FakeNotifier()

    processor = PaymentProcessor(session, gateway=gateway, notifier=notifier)
    await processor.process(payment.id)

    assert gateway.calls == 0
    assert notifier.calls == 0
