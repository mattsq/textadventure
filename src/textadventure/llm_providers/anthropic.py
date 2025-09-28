"""Adapter mapping Anthropic's Messages API onto :class:`LLMClient`."""

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


def _normalise_text_blocks(blocks: Any) -> str:
    if isinstance(blocks, str):
        return blocks
    if isinstance(blocks, Sequence):
        text_parts: list[str] = []
        for item in blocks:
            if isinstance(item, Mapping):
                if item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
        if text_parts:
            return "".join(text_parts)
    raise ValueError("Anthropic response did not contain textual content")


class AnthropicMessagesClient(LLMClient):
    """Concrete :class:`LLMClient` built on top of the official Anthropic SDK."""

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
                from anthropic import Anthropic  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency path
                raise ImportError(
                    "AnthropicMessagesClient requires the 'anthropic' package. Install it with 'pip install anthropic'."
                ) from exc

            init_kwargs: dict[str, Any] = dict(client_options)
            if api_key is not None:
                init_kwargs["api_key"] = api_key
            client = Anthropic(**init_kwargs)
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
            response = self._client.messages.create(  # type: ignore[call-arg]
                model=self._model,
                messages=payload,
                **request_kwargs,
            )
        except Exception as exc:  # pragma: no cover - pass-through error path
            raise LLMClientError("Anthropic completion failed") from exc

        role = _require_str(getattr(response, "role", "assistant"), field_name="role")
        content = _normalise_text_blocks(getattr(response, "content", ""))
        usage = getattr(response, "usage", {}) or {}
        metadata: dict[str, str] = {}
        response_id = getattr(response, "id", None)
        if isinstance(response_id, str) and response_id:
            metadata["id"] = response_id

        return LLMResponse(
            message=LLMMessage(role=role, content=content),
            usage=usage,
            metadata=metadata,
        )


__all__ = ["AnthropicMessagesClient"]
