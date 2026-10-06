"""Pydantic-схемы HTTP API и сообщений брокера."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.models.payment import Currency, PaymentStatus


class PaymentCreateRequest(BaseModel):
    """Тело POST /api/v1/payments."""

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2, examples=["100.50"])
    currency: Currency
    description: str = Field(min_length=1, max_length=1024)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: AnyHttpUrl

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        """Пустая строка из пробелов не считается описанием."""
        cleaned = value.strip()
        if not cleaned:
            msg = "Описание не может быть пустым"
            raise ValueError(msg)
        return cleaned


class PaymentAcceptedResponse(BaseModel):
    """Ответ 202 Accepted: платёж принят в обработку, но ещё не проведён шлюзом."""

    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentDetailsResponse(BaseModel):
    """Полная карточка платежа для GET."""

    model_config = ConfigDict(from_attributes=True)

    payment_id: UUID = Field(validation_alias="id")
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata")
    status: PaymentStatus
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
    webhook_sent_at: datetime | None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        """Decimal в JSON как строка — без ошибок двоичной плавающей точки."""
        return format(value, "f")


class PaymentNewEvent(BaseModel):
    """Сообщение очереди payments.new: consumer'у достаточно payment_id."""

    payment_id: UUID
    event_type: str = "payments.new"

    @classmethod
    def from_payment_id(cls, payment_id: UUID) -> Self:
        """Фабрика payload для outbox."""
        return cls(payment_id=payment_id)


class WebhookPayload(BaseModel):
    """Тело callback'а, который уходит на webhook_url клиента."""

    payment_id: UUID
    status: PaymentStatus
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any]
    processed_at: datetime | None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        """Сумма в webhook тоже строкой, чтобы клиент не потерял копейки."""
        return format(value, "f")
