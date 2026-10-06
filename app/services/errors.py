"""Доменные исключения сервиса платежей."""


class PaymentError(Exception):
    """Базовая ошибка прикладного слоя."""


class PaymentNotFoundError(PaymentError):
    """Платёж с указанным id отсутствует."""


class IdempotencyConflictError(PaymentError):
    """Тот же Idempotency-Key, но другое тело запроса — дубль с другим смыслом."""

    def __init__(self, payment_id: str) -> None:
        self.payment_id = payment_id
        super().__init__("Idempotency-Key уже использован для другого платежа")


class PaymentProcessingError(PaymentError):
    """Сбой обработки сообщения (шлюз уже мог завершиться — смотри статус в БД)."""
