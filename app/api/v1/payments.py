"""HTTP API v1: создание и чтение платежей."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.api.deps import get_payment_service, require_api_key
from app.schemas.payment import (
    PaymentAcceptedResponse,
    PaymentCreateRequest,
    PaymentDetailsResponse,
)
from app.services.errors import IdempotencyConflictError, PaymentNotFoundError
from app.services.payment import PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
    dependencies=[Depends(require_api_key)],
)

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
        description="Обязательный ключ идемпотентности, уникальный на намерение оплаты",
    ),
]


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentAcceptedResponse,
    summary="Создать платёж",
)
async def create_payment(
    payload: PaymentCreateRequest,
    idempotency_key: IdempotencyKey,
    response: Response,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentAcceptedResponse:
    """Принимает платёж в обработку.

    Платёж и запись outbox сохраняются атомарно. В очередь RabbitMQ событие
    попадёт чуть позже — его вычитает фоновый OutboxPublisher.
    Повтор с тем же Idempotency-Key и тем же телом возвращает исходный 202.
    """
    try:
        payment, _replay = await service.create(payload, idempotency_key)
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Idempotency-Key already used by payment {exc.payment_id}",
        ) from exc

    response.headers["Location"] = f"/api/v1/payments/{payment.id}"
    return PaymentAcceptedResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentDetailsResponse,
    summary="Получить платёж",
)
async def get_payment(
    payment_id: UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentDetailsResponse:
    """Возвращает актуальную карточку, включая статус после обработки consumer'ом."""
    try:
        payment = await service.get(payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        ) from exc
    return PaymentDetailsResponse.model_validate(payment)
