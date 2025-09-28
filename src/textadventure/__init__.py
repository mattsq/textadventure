"""Core package for the text adventure framework."""

from .llm import LLMClient, LLMClientError, LLMMessage, LLMResponse, iter_contents
from .llm_provider_registry import LLMProviderRegistry, parse_cli_options
from .story_engine import StoryChoice, StoryEngine, StoryEvent
from .scripted_story_engine import (
    ScriptedStoryEngine,
    load_scenes_from_file,
    load_scenes_from_mapping,
)
from .multi_agent import (
    Agent,
    AgentTrigger,
    AgentTurnResult,
    CoordinatorDebugState,
    MultiAgentCoordinator,
    QueuedAgentMessage,
    ScriptedStoryAgent,
)
from .llm_story_agent import LLMStoryAgent
from .persistence import (
    FileSessionStore,
    InMemorySessionStore,
    SessionSnapshot,
    SessionStore,
)
from .memory import MemoryEntry, MemoryLog, MemoryRequest
from .tools import KnowledgeBaseTool, Tool, ToolResponse
from .world_state import WorldState

__all__ = [
    "WorldState",
    "StoryChoice",
    "StoryEvent",
    "StoryEngine",
    "ScriptedStoryEngine",
    "load_scenes_from_file",
    "load_scenes_from_mapping",
    "Agent",
    "AgentTrigger",
    "AgentTurnResult",
    "ScriptedStoryAgent",
    "MultiAgentCoordinator",
    "CoordinatorDebugState",
    "QueuedAgentMessage",
    "LLMStoryAgent",
    "Tool",
    "ToolResponse",
    "KnowledgeBaseTool",
    "MemoryEntry",
    "MemoryLog",
    "MemoryRequest",
    "LLMClient",
    "LLMClientError",
    "LLMMessage",
    "LLMResponse",
    "LLMProviderRegistry",
    "parse_cli_options",
    "iter_contents",
    "SessionSnapshot",
    "SessionStore",
    "InMemorySessionStore",
    "FileSessionStore",
]
