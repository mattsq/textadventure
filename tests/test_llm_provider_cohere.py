"""Unit tests for :mod:`textadventure.llm_providers.cohere`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from textadventure.llm import LLMClientError, LLMMessage
from textadventure.llm_providers.cohere import CohereChatClient


class _RecordingChat:
    def __init__(self, result: object) -> None:
        self._result = result
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _build_client(result: object) -> tuple[CohereChatClient, _RecordingChat]:
    recorder = _RecordingChat(result)
    client = SimpleNamespace(chat=recorder)
    adapter = CohereChatClient(
        model="command-r",
        client=client,
        default_options={"max_tokens": 128},
    )
    return adapter, recorder


def test_complete_returns_llm_response() -> None:
    response_payload = SimpleNamespace(
        text="Hello",
        role="assistant",
        usage={"tokens": 8},
        response_id="resp-7",
    )
    adapter, recorder = _build_client(response_payload)

    response = adapter.complete(
        [LLMMessage(role="user", content="Hi")], temperature=0.9
    )

    assert recorder.calls == [
        {
            "model": "command-r",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 128,
            "temperature": 0.9,
        }
    ]
    assert response.message.role == "assistant"
    assert response.message.content == "Hello"
    assert response.metadata == {"id": "resp-7"}
    assert response.usage == {"tokens": 8}


def test_complete_supports_message_mapping_payloads() -> None:
    response_payload = {"message": {"content": "Hi there", "role": "assistant"}}
    adapter, _ = _build_client(response_payload)

    response = adapter.complete([LLMMessage(role="user", content="Hi")])

    assert response.message.content == "Hi there"


def test_complete_raises_llmclienterror_on_failure() -> None:
    adapter, recorder = _build_client(RuntimeError("network"))

    with pytest.raises(LLMClientError) as excinfo:
        adapter.complete([LLMMessage(role="user", content="Hi")])

    assert "Cohere completion failed" in str(excinfo.value)
    assert recorder.calls == [
        {
            "model": "command-r",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 128,
        }
    ]


def test_capabilities_report_streaming_support() -> None:
    adapter, _ = _build_client({"text": "Hi"})

    capabilities = adapter.capabilities()

    assert capabilities.supports_streaming()
