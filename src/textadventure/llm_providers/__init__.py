"""Implementations of :class:`~textadventure.llm.LLMClient` for third-party APIs."""

from __future__ import annotations

from .anthropic import AnthropicMessagesClient
from .cohere import CohereChatClient
from .local import LlamaCppClient, TextGenerationInferenceClient
from .openai import OpenAIChatClient
from ..llm_provider_registry import LLMProviderRegistry


def register_builtin_providers(registry: LLMProviderRegistry) -> None:
    """Register the bundled provider adapters with ``registry``."""

    registry.register("openai", lambda **options: OpenAIChatClient(**options))
    registry.register("anthropic", lambda **options: AnthropicMessagesClient(**options))
    registry.register("cohere", lambda **options: CohereChatClient(**options))
    registry.register(
        "text-generation-inference",
        lambda **options: TextGenerationInferenceClient(**options),
    )
    registry.register("tgi", lambda **options: TextGenerationInferenceClient(**options))
    registry.register("llama-cpp", lambda **options: LlamaCppClient(**options))


__all__ = [
    "AnthropicMessagesClient",
    "CohereChatClient",
    "LlamaCppClient",
    "OpenAIChatClient",
    "TextGenerationInferenceClient",
    "register_builtin_providers",
]
