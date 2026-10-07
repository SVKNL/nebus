"""Доставка webhook: успех и исчерпание попыток."""

from unittest.mock import patch

import httpx
import pytest
from app.adapters.webhook import WebhookDeliveryError, WebhookNotifier
from app.models.payment import Payment
from tenacity import wait_none


def _transport(status_code: int) -> httpx.MockTransport:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code)

    return httpx.MockTransport(handler)


async def test_webhook_success_marks_sent(payment: Payment) -> None:
    client = httpx.AsyncClient(transport=_transport(200), base_url="https://merchant.example")
    notifier = WebhookNotifier(client=client)
    await notifier.notify(payment)
    assert payment.webhook_sent_at is not None
    await client.aclose()


async def test_webhook_retries_then_fails(payment: Payment) -> None:
    client = httpx.AsyncClient(transport=_transport(500), base_url="https://merchant.example")
    notifier = WebhookNotifier(client=client)
    with (
        patch("app.adapters.webhook.wait_exponential", return_value=wait_none()),
        pytest.raises(WebhookDeliveryError),
    ):
        await notifier.notify(payment)
    assert payment.webhook_sent_at is None
    await client.aclose()
