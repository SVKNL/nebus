"""Топология RabbitMQ: exchange, очереди и bind.

FastStream сам объявляет очередь только у subscriber'а.
Retry и DLQ никто не слушает, поэтому их нужно объявить явно,
иначе публикация с routing key уходит в пустой direct-exchange и теряется.
"""

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

PAYMENTS_EXCHANGE = "payments"
PAYMENTS_NEW_QUEUE = "payments.new"
PAYMENTS_NEW_ROUTING_KEY = "payments.new"
PAYMENTS_RETRY_QUEUE = "payments.retry"
PAYMENTS_RETRY_ROUTING_KEY = "payments.retry"
PAYMENTS_DLQ = "payments.new.dlq"
PAYMENTS_DLX = "payments.dlx"
PAYMENTS_DLQ_ROUTING_KEY = "payments.new.dlq"

payments_exchange = RabbitExchange(
    PAYMENTS_EXCHANGE,
    type=ExchangeType.DIRECT,
    durable=True,
)

dead_letter_exchange = RabbitExchange(
    PAYMENTS_DLX,
    type=ExchangeType.DIRECT,
    durable=True,
)

# Если consumer упал без ack, брокер не крутит сообщение вечно: после reject оно в DLQ.
payments_new_queue = RabbitQueue(
    PAYMENTS_NEW_QUEUE,
    durable=True,
    routing_key=PAYMENTS_NEW_ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": PAYMENTS_DLX,
        "x-dead-letter-routing-key": PAYMENTS_DLQ_ROUTING_KEY,
    },
)

# TTL задаётся на сообщении (expiration). По истечении брокер возвращает его в payments.new.
retry_queue = RabbitQueue(
    PAYMENTS_RETRY_QUEUE,
    durable=True,
    routing_key=PAYMENTS_RETRY_ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": PAYMENTS_EXCHANGE,
        "x-dead-letter-routing-key": PAYMENTS_NEW_ROUTING_KEY,
    },
)

dead_letter_queue = RabbitQueue(
    PAYMENTS_DLQ,
    durable=True,
    routing_key=PAYMENTS_DLQ_ROUTING_KEY,
)


async def declare_topology(broker: RabbitBroker) -> None:
    """Объявляет exchange, очереди и привязки. Вызов идемпотентен."""
    payments = await broker.declare_exchange(payments_exchange)
    dlx = await broker.declare_exchange(dead_letter_exchange)

    new_queue = await broker.declare_queue(payments_new_queue)
    retry = await broker.declare_queue(retry_queue)
    dlq = await broker.declare_queue(dead_letter_queue)

    await new_queue.bind(payments, routing_key=PAYMENTS_NEW_ROUTING_KEY)
    await retry.bind(payments, routing_key=PAYMENTS_RETRY_ROUTING_KEY)
    await dlq.bind(dlx, routing_key=PAYMENTS_DLQ_ROUTING_KEY)
