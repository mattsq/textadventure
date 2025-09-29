import json
from typing import Mapping, Optional

import pytest

from textadventure.llm import LLMClientError, LLMMessage
from textadventure.llm_providers.local import (
    LlamaCppClient,
    TextGenerationInferenceClient,
)


class _RecordingTransport:
    def __init__(self, response: Mapping[str, object], status: int = 200) -> None:
        self._response = response
        self._status = status
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        url: str,
        data: bytes,
        headers: Mapping[str, str],
        timeout: Optional[float] = None,
    ) -> tuple[int, Mapping[str, str], bytes]:
        self.calls.append(
            {
                "url": url,
                "payload": json.loads(data.decode("utf-8")),
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        return self._status, {}, json.dumps(self._response).encode("utf-8")


def test_tgi_client_issues_request_and_parses_response() -> None:
    transport = _RecordingTransport(
        {
            "generated_text": "Hello world",
            "details": {
                "finish_reason": "length",
                "tokens": {"prompt_tokens": 5, "completion_tokens": 7},
            },
            "model": "tgi-test-model",
        }
    )
    client = TextGenerationInferenceClient(
        base_url="http://localhost:8080",
        default_parameters={"max_new_tokens": 128},
        headers={"X-Test": "1"},
        timeout=12.0,
        transport=transport,
    )

    response = client.complete(
        [
            LLMMessage(role="system", content="You are a poet."),
            LLMMessage(role="user", content="Write a haiku."),
        ],
        temperature=0.2,
    )

    assert transport.calls == [
        {
            "url": "http://localhost:8080/generate",
            "headers": {"X-Test": "1", "Content-Type": "application/json"},
            "timeout": 12.0,
            "payload": {
                "inputs": "[system]\nYou are a poet.\n\nUser: Write a haiku.",
                "parameters": {"max_new_tokens": 128, "temperature": 0.2},
            },
        }
    ]
    assert response.message.role == "assistant"
    assert response.message.content == "Hello world"
    assert response.metadata == {"finish_reason": "length", "model": "tgi-test-model"}
    assert response.usage == {"prompt_tokens": 5, "completion_tokens": 7}


def test_tgi_client_raises_on_non_200_status() -> None:
    transport = _RecordingTransport({"error": "boom"}, status=500)
    client = TextGenerationInferenceClient(
        base_url="http://localhost:8080",
        transport=transport,
    )

    with pytest.raises(LLMClientError):
        client.complete([LLMMessage(role="user", content="Hi")])


class _RecordingLlama:
    def __init__(self, response: Mapping[str, object]) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create_chat_completion(self, **kwargs: object) -> Mapping[str, object]:
        self.calls.append(kwargs)
        return self._response


def test_llama_cpp_client_wraps_create_chat_completion() -> None:
    llama = _RecordingLlama(
        {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello there"},
                }
            ],
            "usage": {"prompt_tokens": 3},
            "id": "llama-123",
            "model": "llama-cpp-test",
        }
    )
    client = LlamaCppClient(client=llama, default_options={"n_predict": 64})

    response = client.complete(
        [LLMMessage(role="user", content="Hello?")],
        temperature=0.4,
    )

    assert len(llama.calls) == 1
    call = llama.calls[0]
    assert call["messages"] == [{"role": "user", "content": "Hello?"}]
    assert call["max_tokens"] == 64  # n_predict is mapped to max_tokens
    assert call["temperature"] == 0.4
    # Allow additional optimization parameters to be present
    assert response.message.content == "Hello there"
    assert response.metadata == {"id": "llama-123", "model": "llama-cpp-test"}
    assert response.usage == {"prompt_tokens": 3}


def test_llama_cpp_client_raises_on_invalid_response() -> None:
    llama = _RecordingLlama({"choices": []})
    client = LlamaCppClient(client=llama)

    with pytest.raises(LLMClientError):
        client.complete([LLMMessage(role="user", content="Hi")])


def test_llama_cpp_client_requires_model_path_without_client() -> None:
    with pytest.raises(ValueError):
        LlamaCppClient()
