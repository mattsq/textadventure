"""Playtest and testing-related Pydantic models for the text adventure API.

This module contains all Pydantic model definitions related to playtesting
functionality, including memory requests, queued messages, world state,
events, errors, and transcript management for WebSocket and HTTP responses.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChoiceResource(BaseModel):
    """Representation of a single scene choice."""

    command: str
    description: str


class MemoryRequestResource(BaseModel):
    """Description of a queued agent memory request."""

    action_limit: int | None = None
    observation_limit: int | None = None


class QueuedMessageResource(BaseModel):
    """Metadata describing a queued coordinator message."""

    origin_agent: str
    trigger_kind: str
    player_input: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    memory_request: MemoryRequestResource | None = None


class PlaytestWorldStateResource(BaseModel):
    """Summary of the playtest world state surfaced via WebSocket."""

    location: str
    inventory: list[str] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    recent_actions: list[str] = Field(default_factory=list)
    recent_observations: list[str] = Field(default_factory=list)
    queued_messages: list[QueuedMessageResource] = Field(default_factory=list)


class PlaytestEventResource(BaseModel):
    """Narrative event broadcast to live preview clients."""

    narration: str
    choices: list[ChoiceResource] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    has_choices: bool


class PlaytestEventMessage(BaseModel):
    """Envelope describing an event message pushed over the WebSocket."""

    type: Literal["event"]
    session_id: str
    event: PlaytestEventResource
    world: PlaytestWorldStateResource


class PlaytestErrorMessage(BaseModel):
    """Error payload returned for invalid playtest commands."""

    type: Literal["error"]
    code: str
    message: str


class PlaytestTranscriptEntryResource(BaseModel):
    """Serialized transcript entry for HTTP and WebSocket responses."""

    turn: int
    player_input: str | None = None
    event: PlaytestEventResource


class PlaytestTranscriptMessage(BaseModel):
    """WebSocket payload returning the current transcript entries."""

    type: Literal["transcript"]
    session_id: str
    entries: list[PlaytestTranscriptEntryResource] = Field(default_factory=list)


class PlaytestTranscriptResponse(BaseModel):
    """HTTP response returning the recorded playtest transcript."""

    session_id: str
    entries: list[PlaytestTranscriptEntryResource] = Field(default_factory=list)


__all__ = [
    "ChoiceResource",
    "MemoryRequestResource",
    "QueuedMessageResource",
    "PlaytestWorldStateResource",
    "PlaytestEventResource",
    "PlaytestEventMessage",
    "PlaytestErrorMessage",
    "PlaytestTranscriptEntryResource",
    "PlaytestTranscriptMessage",
    "PlaytestTranscriptResponse",
]
