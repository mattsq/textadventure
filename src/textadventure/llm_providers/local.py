"""Adapters for self-hosted LLM runtimes such as TGI and llama.cpp."""

from __future__ import annotations

import json
from typing import Any, Mapping, MutableMapping, Protocol, Sequence

from ..llm import (
    LLMCapabilities,
    LLMCapability,
    LLMClient,
    LLMClientError,
    LLMMessage,
    LLMResponse,
)


def _require_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value)!r}")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")
    return stripped


def _coerce_mapping(
    value: Mapping[str, Any] | MutableMapping[str, Any] | None,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("default options must be a mapping of keyword arguments")
    return dict(value)


class _Transport(Protocol):
    """Protocol describing the minimal HTTP transport used by adapters."""

    def __call__(
        self,
        url: str,
        data: bytes,
        headers: Mapping[str, str],
        timeout: float | None = None,
    ) -> tuple[int, Mapping[str, str], bytes]:
        """Send a POST request and return ``(status, headers, body)``."""


def _default_transport(
    url: str,
    data: bytes,
    headers: Mapping[str, str],
    timeout: float | None = None,
) -> tuple[int, Mapping[str, str], bytes]:
    """Send an HTTP POST request using :mod:`urllib`."""

    from urllib import error, request

    req = request.Request(url, data=data, headers=dict(headers), method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:  # type: ignore[arg-type]
            status = int(response.getcode() or 0)
            response_headers = dict(response.headers.items())
            body = response.read()
    except error.URLError as exc:  # pragma: no cover - network failure path
        raise LLMClientError("HTTP request to local runtime failed") from exc

    return status, response_headers, body


def _serialise_messages(messages: Sequence[LLMMessage]) -> str:
    """Serialise chat messages into a plain-text prompt."""

    parts = []
    for message in messages:
        role = message.role or "user"
        if role == "system":
            parts.append(f"[system]\n{message.content}")
        elif role == "assistant":
            parts.append(f"Assistant: {message.content}")
        else:
            parts.append(f"User: {message.content}")
    return "\n\n".join(parts)


class TextGenerationInferenceClient(LLMClient):
    """Adapter that targets Hugging Face Text Generation Inference servers."""

    def __init__(
        self,
        *,
        base_url: str,
        generate_path: str = "/generate",
        default_parameters: Mapping[str, Any] | MutableMapping[str, Any] | None = None,
        headers: Mapping[str, str] | MutableMapping[str, str] | None = None,
        timeout: float | None = None,
        transport: _Transport | None = None,
    ) -> None:
        self._base_url = _require_str(base_url, field_name="base_url").rstrip("/")
        if not generate_path.startswith("/"):
            raise ValueError("generate_path must start with '/' to form a valid URL")
        self._generate_path = generate_path
        self._default_parameters = _coerce_mapping(default_parameters)
        self._headers = dict(headers or {})
        self._headers.setdefault("Content-Type", "application/json")
        self._timeout = timeout
        self._transport: _Transport = transport or _default_transport

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            streaming=LLMCapability(supported=False),
            function_calling=LLMCapability(supported=False),
        )

    def complete(
        self,
        messages: Sequence[LLMMessage],
        *,
        temperature: float | None = None,
    ) -> LLMResponse:
        prompt = _serialise_messages(messages)
        payload: dict[str, Any] = {"inputs": prompt}
        parameters = dict(self._default_parameters)
        if temperature is not None:
            parameters["temperature"] = temperature
        if parameters:
            payload["parameters"] = parameters

        url = f"{self._base_url}{self._generate_path}"
        try:
            status, _, body = self._transport(
                url, json.dumps(payload).encode("utf-8"), self._headers, self._timeout
            )
        except Exception as exc:  # pragma: no cover - delegated error path
            raise LLMClientError("Text Generation Inference request failed") from exc

        if status != 200:
            raise LLMClientError(
                f"Text Generation Inference returned unexpected status {status}"
            )

        try:
            response_payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMClientError(
                "Text Generation Inference response was not valid JSON"
            ) from exc

        if isinstance(response_payload, list):
            # Some deployments return a list of generations, use the first entry.
            if not response_payload:
                raise LLMClientError(
                    "Text Generation Inference returned no generations"
                )
            response_payload = response_payload[0]

        if not isinstance(response_payload, Mapping):
            raise LLMClientError("Text Generation Inference response must be a mapping")

        generated_text = response_payload.get("generated_text")
        if not isinstance(generated_text, str) or not generated_text:
            # The server may return ``generated_texts`` instead.
            generated_texts = response_payload.get("generated_texts")
            if isinstance(generated_texts, Sequence) and generated_texts:
                first_text = generated_texts[0]
                if isinstance(first_text, str) and first_text.strip():
                    generated_text = first_text
        if not isinstance(generated_text, str) or not generated_text:
            raise LLMClientError(
                "Text Generation Inference response did not contain generated text"
            )

        details = response_payload.get("details")
        metadata: dict[str, str] = {}
        usage: dict[str, int] = {}
        if isinstance(details, Mapping):
            finish_reason = details.get("finish_reason")
            if isinstance(finish_reason, str) and finish_reason.strip():
                metadata["finish_reason"] = finish_reason.strip()
            seed = details.get("seed")
            if isinstance(seed, (str, int)):
                metadata["seed"] = str(seed)
            tokens = details.get("tokens")
            if isinstance(tokens, Mapping):
                for key, value in tokens.items():
                    if isinstance(value, (int, float)):
                        usage[str(key)] = int(value)

        model_name = response_payload.get("model")
        if isinstance(model_name, str) and model_name.strip():
            metadata["model"] = model_name.strip()

        return LLMResponse(
            message=LLMMessage(role="assistant", content=generated_text),
            usage=usage,
            metadata=metadata,
        )


class LlamaCppClient(LLMClient):
    """Adapter that wraps the :mod:`llama_cpp` Python bindings."""

    def __init__(
        self,
        *,
        model_path: str | None = None,
        client: Any | None = None,
        default_options: Mapping[str, Any] | MutableMapping[str, Any] | None = None,
        **client_options: Any,
    ) -> None:
        # Optimized defaults for narrative generation
        optimized_defaults = {
            "temperature": 0.7,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "max_tokens": 150,  # Reasonable limit for narration
        }

        if default_options:
            optimized_defaults.update(default_options)

        self._default_options = optimized_defaults

        if client is None:
            if model_path is None:
                raise ValueError(
                    "model_path must be provided when constructing LlamaCppClient without a client"
                )
            try:
                from llama_cpp import Llama  # type: ignore
            except (
                ImportError
            ) as exc:  # pragma: no cover - depends on optional dependency
                raise ImportError(
                    "LlamaCppClient requires the 'llama-cpp-python' package. Install it with 'pip install llama-cpp-python'."
                ) from exc

            init_kwargs = dict(client_options)
            init_kwargs["model_path"] = model_path
            client = Llama(**init_kwargs)
        else:
            if client_options:
                raise TypeError(
                    "client_options cannot be provided when supplying a llama.cpp client instance"
                )
        self._client = client

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            streaming=LLMCapability(supported=False),
            function_calling=LLMCapability(supported=False),
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

        # Build parameters for the API call
        params = dict(self._default_options)
        if temperature is not None:
            params["temperature"] = temperature

        # Create kwargs for create_chat_completion, translating parameter names as needed
        call_kwargs = {}

        # Handle n_predict -> max_tokens mapping for legacy compatibility
        # n_predict takes precedence over max_tokens if both are present
        if "n_predict" in params:
            call_kwargs["max_tokens"] = params["n_predict"]
        elif "max_tokens" in params:
            call_kwargs["max_tokens"] = params["max_tokens"]

        # Add other supported parameters
        for param in [
            "temperature",
            "top_p",
            "repeat_penalty",
            "stream",
            "stop",
            "seed",
        ]:
            if param in params:
                call_kwargs[param] = params[param]

        try:
            response = self._client.create_chat_completion(messages=payload, **call_kwargs)  # type: ignore
        except Exception as exc:  # pragma: no cover - delegated error path
            raise LLMClientError("llama.cpp completion failed") from exc

        if not isinstance(response, Mapping):
            raise LLMClientError("llama.cpp completion response must be a mapping")

        choices = response.get("choices")
        if not isinstance(choices, Sequence) or not choices:
            raise LLMClientError("llama.cpp completion returned no choices")
        first_choice = choices[0]
        if isinstance(first_choice, Mapping):
            message_payload = first_choice.get("message")
        else:
            raise LLMClientError("llama.cpp completion choice must be a mapping")

        if not isinstance(message_payload, Mapping):
            raise LLMClientError("llama.cpp completion choice missing message payload")

        role = message_payload.get("role", "assistant")
        content = message_payload.get("content")
        role_text = _require_str(role, field_name="role")
        content_text = _require_str(content, field_name="content")

        usage_payload = response.get("usage")
        usage: dict[str, int] = {}
        if isinstance(usage_payload, Mapping):
            for key, value in usage_payload.items():  # type: ignore[assignment]
                if isinstance(value, int):
                    usage[str(key)] = value
                elif isinstance(value, float):
                    usage[str(key)] = int(value)

        metadata: dict[str, str] = {}
        response_id = response.get("id")
        if isinstance(response_id, str) and response_id.strip():
            metadata["id"] = response_id.strip()
        model_name = response.get("model")
        if isinstance(model_name, str) and model_name.strip():
            metadata["model"] = model_name.strip()

        return LLMResponse(
            message=LLMMessage(role=role_text, content=content_text),
            usage=usage,
            metadata=metadata,
        )


__all__ = ["TextGenerationInferenceClient", "LlamaCppClient"]
