"""PostgreSQL и RabbitMQ в Docker. Без демона тесты этого пакета пропускаются."""

from __future__ import annotations

import os
from collections.abc import Iterator

import docker
import pytest
from alembic import command
from alembic.config import Config
from app.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.messaging.broker import get_broker
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.rabbitmq import RabbitMqContainer


def _docker_available() -> bool:
    try:
        docker.from_env().ping()
    except Exception:
        return False
    return True


def _reset_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_broker.cache_clear()


@pytest.fixture(scope="session")
def infra() -> Iterator[tuple[str, str]]:
    if not _docker_available():
        pytest.skip("Docker is required for integration tests")

    postgres = PostgresContainer(
        "postgres:16-alpine",
        username="payments",
        password="payments",
        dbname="payments",
    )
    rabbit = RabbitMqContainer("rabbitmq:3.13-alpine")
    postgres.start()
    rabbit.start()
    database_url = postgres.get_connection_url(driver="asyncpg")
    params = rabbit.get_connection_params()
    rabbitmq_url = f"amqp://{rabbit.username}:{rabbit.password}@{params.host}:{params.port}/"
    previous = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "RABBITMQ_URL": os.environ.get("RABBITMQ_URL"),
        "API_KEY": os.environ.get("API_KEY"),
    }
    os.environ["DATABASE_URL"] = database_url
    os.environ["RABBITMQ_URL"] = rabbitmq_url
    os.environ["API_KEY"] = "test-api-key-change-me"
    _reset_caches()
    command.upgrade(Config("alembic.ini"), "head")
    yield database_url, rabbitmq_url
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    _reset_caches()
    rabbit.stop()
    postgres.stop()
