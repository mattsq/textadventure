"""Tests for the LLM abstraction layer."""

import pytest

from typing import Sequence

from textadventure.llm import (
    LLMClient,
    LLMMessage,
    LLMResponse,
    iter_contents,
)


class DummyLLMClient(LLMClient):
    """A simple client implementation for exercising the base helpers."""

    def __init__(self) -> None:
        self.calls: list[list[LLMMessage]] = []

    def complete(
        self, messages: Sequence[LLMMessage], *, temperature: float | None = None
    ) -> LLMResponse:
        self.calls.append(list(messages))
        return LLMResponse(message=messages[-1])


def test_message_validation_and_normalisation() -> None:
    message = LLMMessage(role="User", content="  Hello there  ")
    assert message.role == "user"
    assert message.content == "Hello there"


@pytest.mark.parametrize("field, value", [("role", ""), ("content", "   ")])
def test_message_validation_rejects_empty_strings(field: str, value: str) -> None:
    kwargs = {"role": "user", "content": "hello"}
    kwargs[field] = value

    with pytest.raises(ValueError):
        LLMMessage(**kwargs)  # type: ignore[arg-type]


def test_response_immutability() -> None:
    response = LLMResponse(
        message=LLMMessage(role="assistant", content="Result"),
        usage={"tokens": 42},
        metadata={"model": "gpt"},
    )

    assert response.usage["tokens"] == 42
    assert response.metadata["model"] == "gpt"

    with pytest.raises(TypeError):
        response.usage["tokens"] = 0  # type: ignore[index]

    with pytest.raises(TypeError):
        response.metadata["model"] = "other"  # type: ignore[index]


def test_complete_prompt_helper_constructs_user_message() -> None:
    client = DummyLLMClient()
    client.complete_prompt("Inspect room", temperature=0.1)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert len(call) == 1
    assert call[0].role == "user"
    assert call[0].content == "Inspect room"


def test_iter_contents_returns_message_text() -> None:
    messages = [
        LLMMessage(role="system", content="Rules"),
        LLMMessage(role="user", content="Go north"),
    ]

    assert iter_contents(messages) == ["Rules", "Go north"]

