"""Создание платежа, идемпотентность и публикация outbox в живые Postgres и RabbitMQ."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import aio_pika
import pytest
from app.db.session import get_session_factory
from app.domain.enums import Currency
from app.domain.errors import IdempotencyConflictError
from app.messaging.broker import get_broker
from app.messaging.topology import declare_topology
from app.models.outbox import OutboxEvent
from app.schemas.http import PaymentCreateRequest
from app.services.payment import PaymentService
from app.workers.outbox import OutboxPublisher
from sqlalchemy import func, select

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio(loop_scope="session"),
]


def _payload(amount: str = "15.00") -> PaymentCreateRequest:
    return PaymentCreateRequest(
        amount=Decimal(amount),
        currency=Currency.RUB,
        description="integration",
        metadata={"order": "1"},
        webhook_url="https://example.com/hook",
    )


async def test_create_writes_payment_and_outbox(infra: tuple[str, str]) -> None:
    factory = get_session_factory()
    async with factory() as session:
        payment, replay = await PaymentService(session).create(_payload(), "idem-create")
    assert replay is False

    async with factory() as session:
        events = list(await session.scalars(select(OutboxEvent)))
    assert len(events) == 1
    assert events[0].payment_id == payment.id
    assert events[0].published_at is None


async def test_same_key_is_replay_and_conflict(infra: tuple[str, str]) -> None:
    factory = get_session_factory()
    async with factory() as session:
        first, _replay = await PaymentService(session).create(_payload(), "idem-replay")
    async with factory() as session:
        second, replay = await PaymentService(session).create(_payload(), "idem-replay")
    assert replay is True
    assert second.id == first.id

    async with factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.payment_id == first.id)
        )
    assert count == 1

    async with factory() as session:
        with pytest.raises(IdempotencyConflictError):
            await PaymentService(session).create(_payload("99.00"), "idem-replay")


async def test_parallel_create_with_same_key(infra: tuple[str, str]) -> None:
    factory = get_session_factory()

    async def create() -> object:
        async with factory() as session:
            payment, _replay = await PaymentService(session).create(_payload(), "idem-race")
            return payment.id

    first, second = await asyncio.gather(create(), create())
    assert first == second


async def test_outbox_publishes_to_payments_new(infra: tuple[str, str]) -> None:
    _database_url, rabbitmq_url = infra
    factory = get_session_factory()
    async with factory() as session:
        payment, _replay = await PaymentService(session).create(_payload(), "idem-publish")

    broker = get_broker()
    await broker.start()
    await declare_topology(broker)
    try:
        async with factory() as session:
            published = await OutboxPublisher().publish_batch(session)
        assert published >= 1
        async with factory() as session:
            event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.payment_id == payment.id)
            )
        assert event is not None
        assert event.published_at is not None

        connection = await aio_pika.connect(rabbitmq_url)
        try:
            channel = await connection.channel()
            queue = await channel.declare_queue("payments.new", passive=True)
            found = False
            for _ in range(published):
                incoming = await queue.get(timeout=5, fail=False)
                if incoming is None:
                    break
                if str(payment.id) in incoming.body.decode():
                    found = True
                await incoming.ack()
            assert found
            retry = await channel.declare_queue("payments.retry", passive=True)
            dlq = await channel.declare_queue("payments.new.dlq", passive=True)
            assert retry.name == "payments.retry"
            assert dlq.name == "payments.new.dlq"
        finally:
            await connection.close()
    finally:
        await broker.stop()
