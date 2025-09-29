"""Agent adapter that prompts an LLM to produce narrative events."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .llm import LLMClient, LLMMessage
from .multi_agent import Agent, AgentTrigger, AgentTurnResult
from .story_engine import StoryChoice, StoryEvent
from .world_state import WorldState


def _normalise_limit(value: int | None, *, field_name: str, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int or None, got {type(value)!r}")
    if value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _format_section(title: str, rows: Iterable[str]) -> str:
    items = [line for line in rows if line]
    if not items:
        return f"{title}: (none)"
    bullet_list = "\n".join(f"- {line}" for line in items)
    return f"{title}:\n{bullet_list}"


@dataclass
class LLMStoryAgent(Agent):
    """Agent implementation that uses an :class:`LLMClient` for narration."""

    name: str
    llm_client: LLMClient
    system_prompt: str = (
        "You are an expert interactive fiction narrator. Your role is to enhance and expand "
        "story scenes with vivid, immersive descriptions while maintaining narrative consistency.\n\n"
        "Rules:\n"
        "- Always respond with valid JSON containing 'narration' (required)\n"
        "- 'narration' should be 2-4 sentences of rich, atmospheric description\n"
        "- Add sensory details (sights, sounds, smells, atmosphere) to enhance immersion\n"
        "- Maintain the mood and tone established by the existing story\n"
        "- Never contradict existing world state or previous narration\n"
        "- Optional: include 'choices' array and 'metadata' object if relevant\n\n"
        "Example format: {\"narration\": \"Your enhanced description here\"}"
    )
    temperature: float | None = None
    history_limit: int = 5
    memory_limit: int = 5

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("agent name must be a string")
        stripped = self.name.strip()
        if not stripped:
            raise ValueError("agent name must be non-empty")
        self.name = stripped

        if not isinstance(self.system_prompt, str):
            raise TypeError("system_prompt must be a string")
        system_prompt = self.system_prompt.strip()
        if not system_prompt:
            raise ValueError("system_prompt must be a non-empty string")
        self.system_prompt = system_prompt

        self.history_limit = _normalise_limit(
            self.history_limit,
            field_name="history_limit",
            default=5,
        )
        self.memory_limit = _normalise_limit(
            self.memory_limit,
            field_name="memory_limit",
            default=5,
        )

    def propose_event(
        self,
        world_state: WorldState,
        *,
        trigger: AgentTrigger,
    ) -> AgentTurnResult:
        start_time = time.time()

        messages = self._build_messages(world_state, trigger)
        response = self.llm_client.complete(messages, temperature=self.temperature)

        generation_time = time.time() - start_time

        event = self._parse_response(response.message.content)
        metadata = self._merge_metadata(event.metadata, response.metadata)

        # Add performance metrics to metadata
        if metadata is None:
            metadata = {}
        else:
            metadata = dict(metadata)

        metadata["generation_time"] = f"{generation_time:.2f}s"
        metadata["model_used"] = response.metadata.get("model", "unknown")
        if response.usage:
            metadata["tokens_used"] = str(response.usage.get("total_tokens", "unknown"))

        event_with_metadata = StoryEvent(
            narration=event.narration,
            choices=event.choices,
            metadata=metadata,
        )
        return AgentTurnResult(event=event_with_metadata)

    def _build_messages(
        self, world_state: WorldState, trigger: AgentTrigger
    ) -> Sequence[LLMMessage]:
        context = self._render_context(world_state, trigger)
        instructions = (
            "Return a compact JSON object. Example format: "
            '{"narration": str, "choices": [{"command": str, "description": str}], '
            '"metadata": {str: str}}. Omit keys you do not need.'
        )
        user_prompt = f"{context}\n\n{instructions}"
        return [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

    def _render_context(self, world_state: WorldState, trigger: AgentTrigger) -> str:
        inventory = ", ".join(sorted(world_state.inventory)) or "(empty)"
        history = world_state.history[-self.history_limit :]
        memory_request = trigger.memory_request
        if memory_request is None:
            action_limit = self.memory_limit
            observation_limit = self.memory_limit
        else:
            action_limit = memory_request.resolve_action_limit(self.memory_limit)
            observation_limit = memory_request.resolve_observation_limit(
                self.memory_limit
            )
        actions = world_state.recent_actions(limit=action_limit)
        observations = world_state.recent_observations(limit=observation_limit)

        sections = [
            f"Trigger kind: {trigger.kind}",
        ]
        if trigger.player_input:
            sections.append(f"Player input: {trigger.player_input}")
        if trigger.source_event is not None:
            sections.append("Previous event narration:")
            sections.append(trigger.source_event.narration)
            if trigger.source_event.choices:
                choice_lines = [
                    f"{choice.command}: {choice.description}"
                    for choice in trigger.source_event.choices
                ]
                sections.append(_format_section("Previous choices", choice_lines))

        sections.extend(
            [
                f"Current location: {world_state.location}",
                f"Inventory: {inventory}",
                _format_section("Recent history", history),
                _format_section("Recent player actions", actions),
                _format_section("Recent observations", observations),
            ]
        )

        return "\n".join(sections)

    def _parse_response(self, payload: str) -> StoryEvent:
        text = payload.strip()
        if not text:
            raise ValueError("LLMStoryAgent received an empty response")

        # Try to extract JSON if wrapped in markdown or other text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            # Provide more helpful error context
            preview = text[:200] + "..." if len(text) > 200 else text
            raise ValueError(
                f"LLMStoryAgent expected JSON content from the LLM. "
                f"Received: {preview}"
            ) from exc

        if not isinstance(data, Mapping):
            raise ValueError("LLMStoryAgent response must be a JSON object")

        narration = data.get("narration")
        if not isinstance(narration, str):
            raise ValueError("LLMStoryAgent response is missing 'narration'")

        choices_payload = data.get("choices", [])
        if not isinstance(choices_payload, Sequence) or isinstance(
            choices_payload, (str, bytes)
        ):
            raise ValueError("'choices' must be an array when provided")

        choices: list[StoryChoice] = []
        for entry in choices_payload:
            if not isinstance(entry, Mapping):
                raise ValueError("choice entries must be objects")
            command = entry.get("command")
            description = entry.get("description")
            if not isinstance(command, str) or not isinstance(description, str):
                raise ValueError("choices must include string command and description")
            choices.append(StoryChoice(command=command, description=description))

        metadata_payload = data.get("metadata")
        metadata: Mapping[str, str] | None
        if metadata_payload is None:
            metadata = None
        else:
            if not isinstance(metadata_payload, Mapping):
                raise ValueError("'metadata' must be an object when provided")
            metadata = {str(key): str(value) for key, value in metadata_payload.items()}

        return StoryEvent(
            narration=narration,
            choices=tuple(choices),
            metadata=metadata,
        )

    @staticmethod
    def _merge_metadata(
        event_metadata: Mapping[str, str] | None,
        response_metadata: Mapping[str, str],
    ) -> Mapping[str, str] | None:
        if not response_metadata:
            return event_metadata

        merged: dict[str, str]
        if event_metadata:
            merged = dict(event_metadata)
        else:
            merged = {}

        for key, value in response_metadata.items():
            merged.setdefault(f"llm:{key}", value)

        return merged


__all__ = ["LLMStoryAgent"]
