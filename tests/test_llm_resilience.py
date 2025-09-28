"""Tests covering retry, rate limiting, and error classification helpers."""

from __future__ import annotations

from collections import deque
from typing import Callable, Deque, List

import pytest

from textadventure.llm import (
    FixedIntervalRateLimiter,
    LLMErrorCategory,
    LLMErrorClassifier,
    LLMRetryPolicy,
    call_with_retries,
)


class FakeClock:
    """Deterministic clock used to simulate time progression in tests."""

    def __init__(self) -> None:
        self._now = 0.0

    def __call__(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


@pytest.fixture()
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture()
def fake_sleep(fake_clock: FakeClock) -> Callable[[float], None]:
    sleeps: Deque[float] = deque()

    def _sleep(duration: float) -> None:
        sleeps.append(duration)
        fake_clock.advance(duration)

    _sleep.calls = sleeps  # type: ignore[attr-defined]
    return _sleep


def test_error_classifier_matches_registered_types() -> None:
    classifier = LLMErrorClassifier()
    classifier.register(LLMErrorCategory.TRANSIENT, TimeoutError)
    classifier.register(LLMErrorCategory.RATE_LIMIT, ConnectionError)

    assert classifier.classify(TimeoutError()) is LLMErrorCategory.TRANSIENT
    assert classifier.classify(ConnectionError()) is LLMErrorCategory.RATE_LIMIT
    assert classifier.classify(ValueError()) is LLMErrorCategory.FATAL


def test_error_classifier_validates_exception_types() -> None:
    classifier = LLMErrorClassifier()

    with pytest.raises(ValueError):
        classifier.register(LLMErrorCategory.TRANSIENT)

    with pytest.raises(TypeError):
        classifier.register(LLMErrorCategory.TRANSIENT, object)  # type: ignore[arg-type]


def test_fixed_interval_rate_limiter_enforces_spacing(
    fake_clock: FakeClock, fake_sleep: Callable[[float], None]
) -> None:
    limiter = FixedIntervalRateLimiter(
        min_interval=2.0, clock=fake_clock, sleep=fake_sleep
    )

    limiter.acquire()
    assert list(fake_sleep.calls) == []  # type: ignore[attr-defined]

    limiter.acquire()
    limiter.acquire()

    assert list(fake_sleep.calls) == [2.0, 2.0]  # type: ignore[attr-defined]


def test_call_with_retries_recovers_from_transient_error(
    fake_clock: FakeClock, fake_sleep: Callable[[float], None]
) -> None:
    attempts: List[int] = []

    def operation() -> str:
        attempts.append(len(attempts))
        if len(attempts) == 1:
            raise TimeoutError("temporary glitch")
        return "ok"

    classifier = LLMErrorClassifier()
    classifier.register(LLMErrorCategory.TRANSIENT, TimeoutError)
    policy = LLMRetryPolicy(
        max_attempts=3, initial_backoff=1.0, backoff_multiplier=2.0, jitter=0.0
    )
    limiter = FixedIntervalRateLimiter(
        min_interval=2.0, clock=fake_clock, sleep=fake_sleep
    )

    result = call_with_retries(
        operation,
        retry_policy=policy,
        classifier=classifier,
        rate_limiter=limiter,
        sleep=fake_sleep,
    )

    assert result == "ok"
    assert attempts == [0, 1]
    assert list(fake_sleep.calls) == [1.0, 1.0]  # type: ignore[attr-defined]


def test_call_with_retries_respects_fatal_errors(
    fake_sleep: Callable[[float], None],
) -> None:
    classifier = LLMErrorClassifier()

    def operation() -> None:
        raise ValueError("fatal")

    with pytest.raises(ValueError):
        call_with_retries(operation, classifier=classifier, sleep=fake_sleep)

    assert list(fake_sleep.calls) == []  # type: ignore[attr-defined]


def test_call_with_retries_stops_after_max_attempts(
    fake_sleep: Callable[[float], None],
) -> None:
    classifier = LLMErrorClassifier()
    classifier.register(LLMErrorCategory.TRANSIENT, TimeoutError)
    policy = LLMRetryPolicy(max_attempts=2, initial_backoff=1.0, jitter=0.0)

    def operation() -> None:
        raise TimeoutError("still broken")

    with pytest.raises(TimeoutError):
        call_with_retries(
            operation, retry_policy=policy, classifier=classifier, sleep=fake_sleep
        )

    assert list(fake_sleep.calls) == [1.0]  # type: ignore[attr-defined]
