"""Доменные ошибки. HTTP-коды назначает слой API, а не сервисы."""


class PaymentError(Exception):
    """Базовая ошибка прикладного слоя."""


class PaymentNotFoundError(PaymentError):
    """Платёж с указанным id отсутствует."""


class IdempotencyConflictError(PaymentError):
    """Тот же Idempotency-Key, но другое тело запроса."""

    def __init__(self, payment_id: str) -> None:
        self.payment_id = payment_id
        super().__init__("Idempotency-Key уже использован для другого платежа")


class PaymentProcessingError(PaymentError):
    """Временный сбой обработки: сообщение можно повторить."""


class NonRetryableError(PaymentError):
    """Повтор не поможет (например, платежа нет в БД). Сообщение уходит в DLQ."""
