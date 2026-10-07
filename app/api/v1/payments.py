"""HTTP API v1: создание и чтение платежей."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.deps import get_payment_service, require_api_key
from app.schemas.http import (
    PaymentAcceptedResponse,
    PaymentCreateRequest,
    PaymentDetailsResponse,
)
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
        description="Ключ идемпотентности, уникальный на намерение оплаты",
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
    """Платёж и строка outbox пишутся одной транзакцией. В очередь событие уйдёт relay."""
    payment, _replay = await service.create(payload, idempotency_key)
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
    """Актуальная карточка, включая статус после consumer'а."""
    payment = await service.get(payment_id)
    return PaymentDetailsResponse.model_validate(payment)
