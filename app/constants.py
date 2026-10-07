"""Числа политики обработки. Имена очередей живут рядом с топологией брокера."""

from datetime import timedelta

GATEWAY_MIN_DELAY = timedelta(seconds=2)
GATEWAY_MAX_DELAY = timedelta(seconds=5)
GATEWAY_SUCCESS_RATE = 0.90

MAX_PROCESS_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1
WEBHOOK_MAX_ATTEMPTS = 3

OUTBOX_EVENT_PAYMENTS_NEW = "payments.new"
OUTBOX_BATCH_SIZE = 50
OUTBOX_MAX_PUBLISH_ATTEMPTS = 10
OUTBOX_RETENTION_HOURS = 24
