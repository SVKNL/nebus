"""Контракт исходящего webhook мерчанту."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.domain.enums import Currency, PaymentStatus


class WebhookPayload(BaseModel):
    """Тело POST на webhook_url."""

    payment_id: UUID
    status: PaymentStatus
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any]
    processed_at: datetime | None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        """Сумма строкой, как и в HTTP API."""
        return format(value, "f")
