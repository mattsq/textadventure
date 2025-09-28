"""Tests for the LLM abstraction layer."""

import pytest

from textadventure.llm import LLMMessage, LLMResponse, iter_contents

from .conftest import StubLLMClient


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
    client = StubLLMClient()
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


def test_stub_llm_client_returns_queued_replies(stub_llm_client: StubLLMClient) -> None:
    stub_llm_client.enqueue_reply("First")
    stub_llm_client.enqueue_reply("Second")

    response_one = stub_llm_client.complete([LLMMessage(role="user", content="Hi")])
    response_two = stub_llm_client.complete([LLMMessage(role="user", content="Again")])

    assert response_one.message.content == "First"
    assert response_two.message.content == "Second"
    assert [call[-1].content for call in stub_llm_client.calls] == ["Hi", "Again"]
