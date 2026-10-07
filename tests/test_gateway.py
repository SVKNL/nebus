"""Эмуляция шлюза: управляемый RNG, без реальной паузы 2–5с."""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from app.adapters.gateway import EmulatedPaymentGateway
from app.domain.enums import Currency, PaymentStatus
from app.models.payment import Payment


@pytest.fixture
def pending_payment() -> Payment:
    return Payment(
        id=uuid4(),
        amount=Decimal("1.00"),
        currency=Currency.RUB,
        description="g",
        extra_metadata={},
        status=PaymentStatus.PENDING,
        idempotency_key="g",
        webhook_url="https://example.com/h",
    )


class _ScriptedRng:
    def __init__(self, value: float) -> None:
        self._value = value

    def uniform(self, _a: float, _b: float) -> float:
        return 0.0

    def random(self) -> float:
        return self._value


async def test_gateway_success(pending_payment: Payment) -> None:
    gateway = EmulatedPaymentGateway(success_rate=0.9, rng=_ScriptedRng(0.1))
    with patch("app.adapters.gateway.asyncio.sleep", return_value=None):
        status = await gateway.charge(pending_payment)
    assert status is PaymentStatus.SUCCEEDED


async def test_gateway_failure(pending_payment: Payment) -> None:
    gateway = EmulatedPaymentGateway(success_rate=0.9, rng=_ScriptedRng(0.95))
    with patch("app.adapters.gateway.asyncio.sleep", return_value=None):
        status = await gateway.charge(pending_payment)
    assert status is PaymentStatus.FAILED
