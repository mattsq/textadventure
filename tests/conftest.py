"""Test configuration and utilities for the text adventure project."""

from __future__ import annotations

import sys
from collections import deque
from pathlib import Path
from typing import Deque, Iterable, List, Sequence

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from textadventure.llm import LLMClient, LLMMessage, LLMResponse


class StubLLMClient(LLMClient):
    """A deterministic LLM client used to keep tests reproducible."""

    def __init__(self, *, replies: Iterable[str] | None = None) -> None:
        self.calls: List[List[LLMMessage]] = []
        self._replies: Deque[LLMResponse] = deque()
        if replies:
            for reply in replies:
                self.enqueue_reply(reply)

    def enqueue_reply(self, reply: str) -> None:
        """Queue a canned assistant response for the next call."""

        message = LLMMessage(role="assistant", content=reply)
        self._replies.append(LLMResponse(message=message))

    def complete(
        self, messages: Sequence[LLMMessage], *, temperature: float | None = None
    ) -> LLMResponse:
        self.calls.append(list(messages))
        if self._replies:
            return self._replies.popleft()

        fallback_content = messages[-1].content if messages else ""
        fallback_message = LLMMessage(role="assistant", content=fallback_content)
        return LLMResponse(message=fallback_message)


@pytest.fixture
def stub_llm_client() -> StubLLMClient:
    """Return a stubbed LLM client that records calls and yields canned replies."""

    return StubLLMClient()


__all__ = ["StubLLMClient", "stub_llm_client"]
