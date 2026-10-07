"""Идемпотентность тела запроса."""

from decimal import Decimal

from app.domain.enums import Currency, PaymentStatus
from app.models.payment import Payment
from app.schemas.http import PaymentCreateRequest
from app.services.payment import payloads_equivalent


def _payment(**kwargs: object) -> Payment:
    data = {
        "amount": Decimal("10.00"),
        "currency": Currency.USD,
        "description": "desc",
        "extra_metadata": {"a": 1},
        "status": PaymentStatus.PENDING,
        "idempotency_key": "k",
        "webhook_url": "https://example.com/hook",
    }
    data.update(kwargs)
    return Payment(**data)


def test_payloads_equivalent_true() -> None:
    existing = _payment()
    payload = PaymentCreateRequest(
        amount=Decimal("10.00"),
        currency=Currency.USD,
        description="desc",
        metadata={"a": 1},
        webhook_url="https://example.com/hook",
    )
    assert payloads_equivalent(existing, payload) is True


def test_payloads_equivalent_false_on_amount() -> None:
    existing = _payment()
    payload = PaymentCreateRequest(
        amount=Decimal("11.00"),
        currency=Currency.USD,
        description="desc",
        metadata={"a": 1},
        webhook_url="https://example.com/hook",
    )
    assert payloads_equivalent(existing, payload) is False
