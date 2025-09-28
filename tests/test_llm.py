"""Tests for the LLM abstraction layer."""

from typing import TYPE_CHECKING

import pytest

from textadventure.llm import LLMMessage, LLMResponse, iter_contents

if TYPE_CHECKING:  # pragma: no cover - only used for static analysis
    from tests.conftest import MockLLMClient


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


def test_complete_prompt_helper_constructs_user_message(
    mock_llm_client: "MockLLMClient",
) -> None:
    mock_llm_client.queue_response("Inspecting room")

    response = mock_llm_client.complete_prompt("Inspect room", temperature=0.1)

    assert len(mock_llm_client.calls) == 1
    call = mock_llm_client.calls[0]
    assert len(call) == 1
    assert call[0].role == "user"
    assert call[0].content == "Inspect room"
    assert response.message.content == "Inspecting room"


def test_mock_llm_client_requires_queued_response(
    mock_llm_client: "MockLLMClient",
) -> None:
    with pytest.raises(AssertionError, match="expected a queued response"):
        mock_llm_client.complete([LLMMessage(role="user", content="hello")])


def test_iter_contents_returns_message_text() -> None:
    messages = [
        LLMMessage(role="system", content="Rules"),
        LLMMessage(role="user", content="Go north"),
    ]

    assert iter_contents(messages) == ["Rules", "Go north"]
