"""Маппинг доменных ошибок в HTTP. Хендлеры эндпоинтов остаются без try/except."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import IdempotencyConflictError, PaymentNotFoundError


def register_exception_handlers(application: FastAPI) -> None:
    """409 и 404 из домена. 401 остаётся в зависимости API-ключа."""

    @application.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict(
        _request: Request,
        exc: IdempotencyConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": f"Idempotency-Key already used by payment {exc.payment_id}"},
        )

    @application.exception_handler(PaymentNotFoundError)
    async def payment_not_found(
        _request: Request,
        _exc: PaymentNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Payment not found"})
