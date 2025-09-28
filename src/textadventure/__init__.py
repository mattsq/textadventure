"""Core package for the text adventure framework."""

from .llm import LLMClient, LLMClientError, LLMMessage, LLMResponse, iter_contents
from .story_engine import StoryChoice, StoryEngine, StoryEvent
from .scripted_story_engine import ScriptedStoryEngine
from .persistence import (
    FileSessionStore,
    InMemorySessionStore,
    SessionSnapshot,
    SessionStore,
)
from .memory import MemoryEntry, MemoryLog
from .world_state import WorldState

__all__ = [
    "WorldState",
    "StoryChoice",
    "StoryEvent",
    "StoryEngine",
    "ScriptedStoryEngine",
    "MemoryEntry",
    "MemoryLog",
    "LLMClient",
    "LLMClientError",
    "LLMMessage",
    "LLMResponse",
    "iter_contents",
    "SessionSnapshot",
    "SessionStore",
    "InMemorySessionStore",
    "FileSessionStore",
]
