"""Декларативная база SQLAlchemy 2.0."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Общий предок моделей: нужен Alembic для autogenerate и metadata."""
