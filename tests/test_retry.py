"""Юнит-тесты политики retry и DLQ."""

from app.messaging.retry import parse_attempt, retry_delay_seconds, should_dead_letter


def test_parse_attempt_defaults_and_invalid() -> None:
    assert parse_attempt(None) == 0
    assert parse_attempt({}) == 0
    assert parse_attempt({"x-attempt": "2"}) == 2
    assert parse_attempt({"x-attempt": "nope"}) == 0


def test_exponential_delay() -> None:
    assert retry_delay_seconds(0) == 1
    assert retry_delay_seconds(1) == 2
    assert retry_delay_seconds(2) == 4


def test_dead_letter_on_third_attempt() -> None:
    assert should_dead_letter(0) is False
    assert should_dead_letter(1) is False
    assert should_dead_letter(2) is True
