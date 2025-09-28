"""Adapter that exposes OpenAI's chat completion API via :class:`LLMClient`."""

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


def _extract_attr(container: Any, name: str, default: Any | None = None) -> Any:
    if isinstance(container, Mapping):
        return container.get(name, default)
    return getattr(container, name, default)


def _normalise_message_content(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, Sequence):
        text_parts: list[str] = []
        for item in payload:
            if isinstance(item, Mapping) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        if text_parts:
            return "".join(text_parts)
    raise ValueError("OpenAI response did not include textual content")


class OpenAIChatClient(LLMClient):
    """Concrete :class:`LLMClient` powered by the OpenAI Python SDK."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        organization: str | None = None,
        client: Any | None = None,
        default_options: Mapping[str, Any] | MutableMapping[str, Any] | None = None,
        **client_options: Any,
    ) -> None:
        self._model = _require_str(model, field_name="model")
        self._default_options = _coerce_mapping(default_options)

        if client is None:
            try:
                from openai import OpenAI  # type: ignore
            except (
                ImportError
            ) as exc:  # pragma: no cover - depends on optional dependency
                raise ImportError(
                    "OpenAIChatClient requires the 'openai' package. Install it with 'pip install openai'."
                ) from exc

            init_kwargs: dict[str, Any] = dict(client_options)
            if api_key is not None:
                init_kwargs["api_key"] = api_key
            if organization is not None:
                init_kwargs["organization"] = organization
            client = OpenAI(**init_kwargs)
        else:
            if client_options:
                raise TypeError(
                    "client_options cannot be provided when supplying a client instance"
                )
        self._client = client

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            streaming=LLMCapability(supported=True),
            function_calling=LLMCapability(supported=True),
        )

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

        payload_param: Any = payload

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=payload_param,
                **request_kwargs,
            )
        except Exception as exc:  # pragma: no cover - pass-through error path
            raise LLMClientError("OpenAI completion failed") from exc

        choices = _extract_attr(response, "choices")
        if not choices:
            raise LLMClientError("OpenAI completion returned no choices")
        first_choice = choices[0]
        message_payload = _extract_attr(first_choice, "message")
        if message_payload is None:
            raise LLMClientError("OpenAI completion missing message payload")

        role = _require_str(
            _extract_attr(message_payload, "role", "assistant"), field_name="role"
        )
        content = _normalise_message_content(_extract_attr(message_payload, "content"))

        usage = _extract_attr(response, "usage", {}) or {}
        metadata: dict[str, str] = {}
        response_id = _extract_attr(response, "id")
        model_name = _extract_attr(response, "model")
        if isinstance(response_id, str) and response_id:
            metadata["id"] = response_id
        if isinstance(model_name, str) and model_name:
            metadata["model"] = model_name

        return LLMResponse(
            message=LLMMessage(role=role, content=content),
            usage=usage,
            metadata=metadata,
        )


__all__ = ["OpenAIChatClient"]
