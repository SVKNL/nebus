"""Валидация входных схем API."""

from decimal import Decimal

import pytest
from app.schemas.payment import PaymentCreateRequest
from pydantic import ValidationError


def test_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError):
        PaymentCreateRequest(
            amount=Decimal("0.00"),
            currency="RUB",
            description="x",
            webhook_url="https://example.com/hook",
        )


def test_rejects_blank_description() -> None:
    with pytest.raises(ValidationError):
        PaymentCreateRequest(
            amount=Decimal("1.00"),
            currency="EUR",
            description="   ",
            webhook_url="https://example.com/hook",
        )


def test_accepts_valid_payload() -> None:
    dto = PaymentCreateRequest(
        amount=Decimal("1.20"),
        currency="USD",
        description="ok",
        metadata={"k": "v"},
        webhook_url="https://example.com/hook",
    )
    assert dto.currency.value == "USD"
