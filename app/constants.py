"""Константы доменной логики: шлюз, retry, очереди RabbitMQ."""

from datetime import timedelta

# Имитация внешнего платёжного шлюза: задержка и вероятность успеха.
GATEWAY_MIN_DELAY = timedelta(seconds=2)
GATEWAY_MAX_DELAY = timedelta(seconds=5)
GATEWAY_SUCCESS_RATE = 0.90

# Повторные попытки обработки сообщения и отправки webhook.
# Задержки: 1с, 2с, 4с — классический экспоненциальный backoff 2^n.
MAX_PROCESS_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1
WEBHOOK_MAX_ATTEMPTS = 3

# Топология брокера: основная очередь, очередь отложенного retry и DLQ.
PAYMENTS_EXCHANGE = "payments"
PAYMENTS_NEW_QUEUE = "payments.new"
PAYMENTS_NEW_ROUTING_KEY = "payments.new"
PAYMENTS_RETRY_QUEUE = "payments.retry"
PAYMENTS_RETRY_ROUTING_KEY = "payments.retry"
PAYMENTS_DLQ = "payments.new.dlq"
PAYMENTS_DLX = "payments.dlx"
PAYMENTS_DLQ_ROUTING_KEY = "payments.new.dlq"

OUTBOX_EVENT_PAYMENTS_NEW = "payments.new"
OUTBOX_BATCH_SIZE = 50
