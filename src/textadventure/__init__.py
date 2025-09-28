"""Core package for the text adventure framework."""

from .llm import LLMClient, LLMClientError, LLMMessage, LLMResponse, iter_contents
from .story_engine import StoryChoice, StoryEngine, StoryEvent
from .scripted_story_engine import ScriptedStoryEngine
from .multi_agent import (
    Agent,
    AgentTrigger,
    AgentTurnResult,
    MultiAgentCoordinator,
    ScriptedStoryAgent,
)
from .persistence import (
    FileSessionStore,
    InMemorySessionStore,
    SessionSnapshot,
    SessionStore,
)
from .memory import MemoryEntry, MemoryLog
from .tools import KnowledgeBaseTool, Tool, ToolResponse
from .world_state import WorldState

__all__ = [
    "WorldState",
    "StoryChoice",
    "StoryEvent",
    "StoryEngine",
    "ScriptedStoryEngine",
    "Agent",
    "AgentTrigger",
    "AgentTurnResult",
    "ScriptedStoryAgent",
    "MultiAgentCoordinator",
    "Tool",
    "ToolResponse",
    "KnowledgeBaseTool",
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
