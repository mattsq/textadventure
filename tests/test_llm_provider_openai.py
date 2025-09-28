"""Unit tests for :mod:`textadventure.llm_providers.openai`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from textadventure.llm import LLMMessage, LLMClientError
from textadventure.llm_providers.openai import OpenAIChatClient


class _RecordingCreate:
    def __init__(self, result: object) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _build_client(result: object) -> tuple[OpenAIChatClient, _RecordingCreate]:
    create = _RecordingCreate(result)
    client = SimpleNamespace(chat=SimpleNamespace(completions=create))
    adapter = OpenAIChatClient(
        model="gpt-4o-mini",
        client=client,
        default_options={"max_tokens": 32},
    )
    return adapter, create


def test_complete_returns_llm_response() -> None:
    response_payload = SimpleNamespace(
        choices=[{"message": {"role": "assistant", "content": "Hello"}}],
        usage={"prompt_tokens": 5},
        id="resp-123",
        model="gpt-4o-mini",
    )
    adapter, recorder = _build_client(response_payload)

    response = adapter.complete(
        [LLMMessage(role="user", content="Hi")], temperature=0.3
    )

    assert recorder.calls == [
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 32,
            "temperature": 0.3,
        }
    ]
    assert response.message.role == "assistant"
    assert response.message.content == "Hello"
    assert response.metadata == {"id": "resp-123", "model": "gpt-4o-mini"}
    assert response.usage == {"prompt_tokens": 5}


def test_complete_raises_llmclienterror_on_failure() -> None:
    adapter, recorder = _build_client(RuntimeError("boom"))

    with pytest.raises(LLMClientError) as excinfo:
        adapter.complete([LLMMessage(role="user", content="Hi")])

    assert "OpenAI completion failed" in str(excinfo.value)
    assert recorder.calls == [
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 32,
        }
    ]


def test_capabilities_surface_supported_features() -> None:
    adapter, _ = _build_client(
        SimpleNamespace(
            choices=[{"message": {"role": "assistant", "content": "Hi"}}],
        )
    )

    capabilities = adapter.capabilities()

    assert capabilities.supports_streaming()
    assert capabilities.supports_function_calling()
