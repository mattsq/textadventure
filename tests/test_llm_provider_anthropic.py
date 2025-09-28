"""Unit tests for :mod:`textadventure.llm_providers.anthropic`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from textadventure.llm import LLMClientError, LLMMessage
from textadventure.llm_providers.anthropic import AnthropicMessagesClient


class _RecordingMessages:
    def __init__(self, result: object) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _build_client(result: object) -> tuple[AnthropicMessagesClient, _RecordingMessages]:
    recorder = _RecordingMessages(result)
    client = SimpleNamespace(messages=SimpleNamespace(create=recorder.create))
    adapter = AnthropicMessagesClient(
        model="claude-3-sonnet",
        client=client,
        default_options={"max_tokens": 256},
    )
    return adapter, recorder


def test_complete_returns_llm_response() -> None:
    response_payload = SimpleNamespace(
        role="assistant",
        content=[{"type": "text", "text": "Hello"}],
        usage={"input_tokens": 12},
        id="msg_42",
    )
    adapter, recorder = _build_client(response_payload)

    response = adapter.complete(
        [LLMMessage(role="user", content="Hi")], temperature=0.2
    )

    assert recorder.calls == [
        {
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 256,
            "temperature": 0.2,
        }
    ]
    assert response.message.role == "assistant"
    assert response.message.content == "Hello"
    assert response.usage == {"input_tokens": 12}
    assert response.metadata == {"id": "msg_42"}


def test_complete_raises_llmclienterror_on_failure() -> None:
    adapter, recorder = _build_client(RuntimeError("oops"))

    with pytest.raises(LLMClientError) as excinfo:
        adapter.complete([LLMMessage(role="user", content="Hi")])

    assert "Anthropic completion failed" in str(excinfo.value)
    assert recorder.calls == [
        {
            "model": "claude-3-sonnet",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 256,
        }
    ]


def test_capabilities_report_streaming_support() -> None:
    adapter, _ = _build_client(
        SimpleNamespace(role="assistant", content=[{"type": "text", "text": "Hi"}])
    )

    capabilities = adapter.capabilities()

    assert capabilities.supports_streaming()
    assert not capabilities.supports_function_calling()
