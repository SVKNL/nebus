"""Объявление обменников и очередей RabbitMQ для FastStream."""

from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

from app.constants import (
    PAYMENTS_DLQ,
    PAYMENTS_DLQ_ROUTING_KEY,
    PAYMENTS_DLX,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    PAYMENTS_NEW_ROUTING_KEY,
    PAYMENTS_RETRY_QUEUE,
    PAYMENTS_RETRY_ROUTING_KEY,
)

# Основной обменник доменных событий платежей.
payments_exchange = RabbitExchange(
    PAYMENTS_EXCHANGE,
    type=ExchangeType.DIRECT,
    durable=True,
)

# DLX принимает сообщения, которые мы явно отправляем в DLQ после 3 попыток,
# и (на случай reject) сообщения, отвергнутые брокером.
dead_letter_exchange = RabbitExchange(
    PAYMENTS_DLX,
    type=ExchangeType.DIRECT,
    durable=True,
)

# Очередь retry: TTL задаётся на каждом сообщении (expiration),
# после истечения брокер возвращает его в payments через DLX этой очереди.
retry_queue = RabbitQueue(
    PAYMENTS_RETRY_QUEUE,
    durable=True,
    routing_key=PAYMENTS_RETRY_ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": PAYMENTS_EXCHANGE,
        "x-dead-letter-routing-key": PAYMENTS_NEW_ROUTING_KEY,
    },
)

payments_new_queue = RabbitQueue(
    PAYMENTS_NEW_QUEUE,
    durable=True,
    routing_key=PAYMENTS_NEW_ROUTING_KEY,
)

dead_letter_queue = RabbitQueue(
    PAYMENTS_DLQ,
    durable=True,
    routing_key=PAYMENTS_DLQ_ROUTING_KEY,
)
