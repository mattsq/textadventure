"""Adapter wiring Cohere's Chat API into the :class:`LLMClient` interface."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

from ..llm import (
    LLMCapabilities,
    LLMCapability,
    LLMClient,
    LLMClientError,
    LLMMessage,
    LLMResponse,
)


def _require_str(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value)!r}")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")
    return stripped


def _coerce_mapping(
    value: Mapping[str, Any] | MutableMapping[str, Any] | None,
) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("default options must be a mapping of keyword arguments")
    return dict(value)


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    message = getattr(response, "message", None)
    if isinstance(message, Mapping):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        text_field = message.get("text")
        if isinstance(text_field, str) and text_field.strip():
            return text_field
    if isinstance(response, Mapping):
        message_mapping = response.get("message")
        if isinstance(message_mapping, Mapping):
            content = message_mapping.get("content")
            if isinstance(content, str) and content.strip():
                return content
            text_field = message_mapping.get("text")
            if isinstance(text_field, str) and text_field.strip():
                return text_field
        for key in ("text", "content"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value
    raise ValueError("Cohere response did not include textual content")


class CohereChatClient(LLMClient):
    """Concrete :class:`LLMClient` backed by the Cohere Python SDK."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        client: Any | None = None,
        default_options: Mapping[str, Any] | MutableMapping[str, Any] | None = None,
        **client_options: Any,
    ) -> None:
        self._model = _require_str(model, field_name="model")
        self._default_options = _coerce_mapping(default_options)

        if client is None:
            try:
                import cohere  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency path
                raise ImportError(
                    "CohereChatClient requires the 'cohere' package. Install it with 'pip install cohere'."
                ) from exc

            init_kwargs: dict[str, Any] = dict(client_options)
            if api_key is not None:
                init_kwargs["api_key"] = api_key
            client = cohere.Client(**init_kwargs)
        else:
            if client_options:
                raise TypeError(
                    "client_options cannot be provided when supplying a client instance"
                )
        self._client = client

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(streaming=LLMCapability(supported=True))

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
    ) -> LLMResponse:
        payload = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        request_kwargs = dict(self._default_options)
        if temperature is not None:
            request_kwargs["temperature"] = temperature

        try:
            response = self._client.chat(  # type: ignore[call-arg]
                model=self._model,
                messages=payload,
                **request_kwargs,
            )
        except Exception as exc:  # pragma: no cover - pass-through error path
            raise LLMClientError("Cohere completion failed") from exc

        content = _extract_text(response)
        role = _require_str(getattr(response, "role", "assistant"), field_name="role")
        usage = getattr(response, "usage", {}) or {}
        metadata: dict[str, str] = {}
        response_id = getattr(response, "response_id", None)
        if isinstance(response_id, str) and response_id:
            metadata["id"] = response_id

        return LLMResponse(
            message=LLMMessage(role=role, content=content),
            usage=usage,
            metadata=metadata,
        )


__all__ = ["CohereChatClient"]
