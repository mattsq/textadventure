"""Test configuration for the text adventure project."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from textadventure.llm import LLMClient, LLMMessage, LLMResponse


class MockLLMClient(LLMClient):
    """Deterministic LLM client used in tests to avoid real API calls."""

    def __init__(
        self,
        responses: Sequence[LLMResponse | str] | None = None,
    ) -> None:
        self.calls: list[list[LLMMessage]] = []
        self._responses: list[LLMResponse] = []

        if responses:
            for response in responses:
                self.queue_response(response)

    def queue_response(
        self,
        response: LLMResponse | str,
        *,
        role: str = "assistant",
        usage: Mapping[str, int] | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Append a response that will be returned on the next call."""

        if isinstance(response, LLMResponse):
            payload = response
        else:
            message = LLMMessage(role=role, content=response)
            payload = LLMResponse(
                message=message,
                usage=dict(usage or {}),
                metadata=dict(metadata or {}),
            )

        self._responses.append(payload)

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
    ) -> LLMResponse:
        del temperature  # This mock ignores sampling parameters.

        self.calls.append(list(messages))
        if not self._responses:
            raise AssertionError(
                "MockLLMClient expected a queued response but none remain",
            )

        return self._responses.pop(0)


@pytest.fixture()
def mock_llm_client() -> MockLLMClient:
    """Return a deterministic mock client for use in tests."""

    return MockLLMClient()


@pytest.fixture()
def make_mock_llm_client() -> Any:
    """Factory fixture for creating mock LLM clients with canned responses."""

    def _factory(
        responses: Sequence[LLMResponse | str] | None = None,
    ) -> MockLLMClient:
        return MockLLMClient(responses=responses)

    return _factory


__all__ = ["MockLLMClient", "mock_llm_client", "make_mock_llm_client"]
