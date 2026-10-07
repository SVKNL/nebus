"""Общие фикстуры: окружение должно существовать до импорта Settings."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

os.environ.setdefault("API_KEY", "test-api-key-change-me")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://payments:payments@localhost:5432/payments",
)
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

from app.domain.enums import Currency, PaymentStatus
from app.main import create_app
from app.models.payment import Payment


@pytest.fixture
def api_key() -> str:
    return "test-api-key-change-me"


@pytest.fixture
def payment() -> Payment:
    return Payment(
        id=uuid4(),
        amount=Decimal("100.50"),
        currency=Currency.RUB,
        description="Тестовая оплата",
        extra_metadata={"order_id": "42"},
        status=PaymentStatus.PENDING,
        idempotency_key="idem-1",
        webhook_url="https://merchant.example/hooks/payments",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def app():
    return create_app(with_lifespan=False)


@pytest.fixture
async def client(app, api_key: str) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        async_client.headers["X-API-Key"] = api_key
        yield async_client
