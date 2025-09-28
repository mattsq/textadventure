# LLM Capability Schema

The `textadventure.llm` module now exposes a capability schema that each LLM
integration can use to advertise optional features such as streaming, structured
function calling, and tool invocation. These descriptors allow the rest of the
runtime to negotiate behaviour without having to special-case individual
providers.

## Data Model Overview

* `LLMCapability` – records whether a feature is supported and lets providers
  attach additional metadata (e.g., supported streaming modes).
* `LLMToolDescription` – captures the shape of a callable tool, including a
  normalised name, human readable description, and a JSON-schema-like parameter
  definition.
* `LLMCapabilities` – aggregates the optional features exposed by a provider.
  Helper methods (`supports_streaming`, `supports_function_calling`, and
  `has_tools`) simplify downstream feature negotiation, while `describe_tool`
  offers case-insensitive lookups for specific tool definitions.

All mappings exposed by these dataclasses are immutable `Mapping` instances so
consumers can safely share them without defensive copying.

## Advertising Capabilities from Clients

Every `LLMClient` subclass can override the new `capabilities()` method to
return the features it implements. Providers that do not support optional
behaviour may rely on the default implementation, which reports a capability set
with streaming, function calling, and tool support disabled.

```python
from textadventure.llm import (
    LLMCapabilities,
    LLMCapability,
    LLMClient,
    LLMToolDescription,
)


class StreamingClient(LLMClient):
    def __init__(self) -> None:
        self._capabilities = LLMCapabilities(
            streaming=LLMCapability(supported=True, metadata={"mode": "delta"}),
            function_calling=LLMCapability(supported=True, metadata={"format": "json"}),
            tools={
                "lore_lookup": LLMToolDescription(
                    name="Lore Lookup",
                    description="Return encyclopaedia entries by topic",
                    parameters_schema={
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "Query to search"}
                        },
                        "required": ["topic"],
                    },
                )
            },
        )

    def capabilities(self) -> LLMCapabilities:
        return self._capabilities
```

Downstream agents can inspect the returned `LLMCapabilities` instance to decide
whether to request streaming responses, issue function calls, or invoke tools.
When a capability is not supported, the helper methods return `False` and tool
lookups yield `None`, allowing fallbacks without resorting to exception-driven
control flow.

## Configuration Examples

Provider integrations can expose configuration knobs through the capability
metadata fields. For example:

* A streaming client might set `metadata={"mode": "event-stream"}` to signal
  that responses arrive as SSE events.
* A function-calling provider can document supported schema formats via
  `metadata={"format": "json_schema"}`.
* Tool descriptions can advertise parameter types with nested objects, required
  arrays, and default values to align with OpenAI-compatible tool definitions.

These metadata values should be documented in the adapter-specific modules so
operators know how to enable or disable advanced behaviour such as temperature
controls, caching, or safety filters.
