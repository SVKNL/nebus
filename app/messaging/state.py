"""Живое ли соединение с RabbitMQ. HTTP от этого не зависит."""


class BrokerState:
    """Флаг для /ready. Его ставит фоновый цикл подключения."""

    def __init__(self) -> None:
        self.connected = False


broker_state = BrokerState()
