"""HTTP API: авторизация, 202, 404, 409."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
from app.api.deps import get_payment_service
from app.models.payment import Payment, PaymentStatus
from app.services.errors import IdempotencyConflictError, PaymentNotFoundError


async def test_health_without_api_key(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_requires_api_key(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/payments",
            headers={"Idempotency-Key": "k"},
            json={
                "amount": "10.00",
                "currency": "RUB",
                "description": "x",
                "webhook_url": "https://example.com/h",
            },
        )
    assert response.status_code == 401


async def test_create_payment_accepted(app, client, payment: Payment) -> None:
    service = AsyncMock()
    service.create = AsyncMock(return_value=(payment, False))
    app.dependency_overrides[get_payment_service] = lambda: service
    response = await client.post(
        "/api/v1/payments",
        headers={"Idempotency-Key": "idem-1"},
        json={
            "amount": "100.50",
            "currency": "RUB",
            "description": "Тестовая оплата",
            "metadata": {"order_id": "42"},
            "webhook_url": "https://merchant.example/hooks/payments",
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 202
    body = response.json()
    assert body["payment_id"] == str(payment.id)
    assert body["status"] == "pending"
    assert response.headers["location"] == f"/api/v1/payments/{payment.id}"


async def test_create_idempotency_conflict(app, client) -> None:
    service = AsyncMock()
    service.create = AsyncMock(side_effect=IdempotencyConflictError(str(uuid4())))
    app.dependency_overrides[get_payment_service] = lambda: service
    response = await client.post(
        "/api/v1/payments",
        headers={"Idempotency-Key": "idem-1"},
        json={
            "amount": "1.00",
            "currency": "USD",
            "description": "x",
            "webhook_url": "https://example.com/h",
        },
    )
    app.dependency_overrides.clear()
    assert response.status_code == 409


async def test_get_not_found(app, client) -> None:
    service = AsyncMock()
    service.get = AsyncMock(side_effect=PaymentNotFoundError)
    app.dependency_overrides[get_payment_service] = lambda: service
    response = await client.get(f"/api/v1/payments/{uuid4()}")
    app.dependency_overrides.clear()
    assert response.status_code == 404


async def test_get_payment(app, client, payment: Payment) -> None:
    payment.status = PaymentStatus.SUCCEEDED
    payment.processed_at = datetime.now(UTC)
    service = AsyncMock()
    service.get = AsyncMock(return_value=payment)
    app.dependency_overrides[get_payment_service] = lambda: service
    response = await client.get(f"/api/v1/payments/{payment.id}")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == "100.50"
    assert body["metadata"] == {"order_id": "42"}
