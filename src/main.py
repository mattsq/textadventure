"""Command-line entry point for the text adventure prototype."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence, TextIO

from textadventure import (
    FileSessionStore,
    LLMProviderRegistry,
    LLMStoryAgent,
    MultiAgentCoordinator,
    ScriptedStoryAgent,
    SessionSnapshot,
    SessionStore,
    StoryEngine,
    StoryEvent,
    WorldState,
)
from textadventure.llm_providers import register_builtin_providers
from textadventure.scripted_story_engine import ScriptedStoryEngine


class TranscriptLogger:
    """Structured writer that records CLI transcripts for debugging."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._turn = 0

    def log_player_input(self, text: str) -> None:
        """Record the player's latest command."""

        formatted = text if text else "(empty)"
        self._write(f"Player input: {formatted}")
        self._stream.flush()

    def log_event(self, event: StoryEvent) -> None:
        """Record a story event's narration, choices, and metadata."""

        self._turn += 1
        self._write("")
        self._write(f"=== Turn {self._turn} ===")
        self._write("Narration:")
        for line in event.narration.splitlines() or ("",):
            self._write(f"  {line}")

        metadata = event.metadata
        if metadata:
            self._write("Metadata:")
            for key, value in sorted(metadata.items()):
                self._write(f"  {key}: {value}")
        else:
            self._write("Metadata: (none)")

        if event.choices:
            self._write("Choices:")
            for choice in event.choices:
                self._write(f"  [{choice.command}] {choice.description}")
        else:
            self._write("Choices: (none)")

        self._stream.flush()

    def _write(self, text: str) -> None:
        self._stream.write(f"{text}\n")


def run_cli(
    engine: StoryEngine,
    world: WorldState,
    *,
    session_store: SessionStore | None = None,
    autoload_session: str | None = None,
    transcript_logger: TranscriptLogger | None = None,
) -> None:
    """Drive a very small interactive loop using ``input``/``print``."""

    print("Welcome to the Text Adventure prototype!")
    print("Type 'quit' at any time to end the session.")
    if session_store is not None:
        print("Type 'save <name>' or 'load <name>' to manage checkpoints.\n")
    else:
        print()

    def _capture_event(new_event: StoryEvent) -> StoryEvent:
        world.remember_observation(new_event.narration)
        if transcript_logger is not None:
            transcript_logger.log_event(new_event)
        return new_event

    event: StoryEvent | None = None
    if session_store is not None and autoload_session:
        try:
            snapshot = session_store.load(autoload_session)
        except KeyError:
            print(
                f"No saved session named '{autoload_session}' was found. "
                "Starting a new adventure.\n"
            )
        else:
            snapshot.apply_to_world(world)
            print(f"Loaded session '{autoload_session}'.\n")
            event = _capture_event(engine.propose_event(world))

    if event is None:
        event = _capture_event(engine.propose_event(world))

    while True:
        print(engine.format_event(event))
        if not event.has_choices:
            print("\nThe story has reached a natural stopping point.")
            break

        try:
            raw_input = input("\n> ")
        except EOFError:
            print("\n\nReached end of input. Until next time!")
            break
        except KeyboardInterrupt:
            print("\n\nInterrupted. Your progress is saved in spirit!")
            break

        player_input = raw_input.strip()
        if transcript_logger is not None:
            transcript_logger.log_player_input(player_input)
        if not player_input:
            event = _capture_event(engine.propose_event(world))
            continue

        command, _, argument = player_input.partition(" ")
        command_lower = command.lower()
        lowered = player_input.lower()
        if lowered in {"quit", "exit"}:
            print("\nThanks for playing!")
            break

        if command_lower == "save":
            if session_store is None:
                print("\nSession persistence is not configured. Saving is unavailable.")
            else:
                session_id = argument.strip()
                if not session_id:
                    print("\nUsage: save <session-id>")
                else:
                    session_store.save(session_id, SessionSnapshot.capture(world))
                    print(f"\nSaved session '{session_id}'.")
            continue

        if command_lower == "load":
            if session_store is None:
                print(
                    "\nSession persistence is not configured. Loading is unavailable."
                )
            else:
                session_id = argument.strip()
                if not session_id:
                    print("\nUsage: load <session-id>")
                else:
                    try:
                        snapshot = session_store.load(session_id)
                    except KeyError:
                        print(f"\nNo saved session named '{session_id}' was found.")
                    else:
                        snapshot.apply_to_world(world)
                        print(f"\nLoaded session '{session_id}'.")
                        event = _capture_event(engine.propose_event(world))
            continue

        if command_lower == "status":
            print("\n=== Adventure Status ===")
            print(f"Location: {world.location}")
            inventory = sorted(world.inventory)
            if inventory:
                print("Inventory: " + ", ".join(inventory))
            else:
                print("Inventory: (empty)")

            debug_snapshot_fn = getattr(engine, "debug_snapshot", None)
            print("Queued agent messages:")
            if callable(debug_snapshot_fn):
                snapshot = debug_snapshot_fn()
                if snapshot.queued_messages:
                    for message in snapshot.queued_messages:
                        details: list[str] = [f"kind={message.trigger_kind}"]
                        if message.player_input:
                            details.append(f"player_input={message.player_input}")
                        if message.metadata:
                            metadata_text = ", ".join(
                                f"{key}={value}"
                                for key, value in sorted(message.metadata.items())
                            )
                            details.append(f"metadata={{{metadata_text}}}")
                        joined = ", ".join(details)
                        print(f"  - from {message.origin_agent} ({joined})")
                else:
                    print("  (none)")
            else:
                print("  (unavailable)")

            if session_store is None:
                print("Pending saves: (persistence disabled)")
            else:
                sessions = sorted(session_store.list_sessions())
                if sessions:
                    print("Pending saves: " + ", ".join(sessions))
                else:
                    print("Pending saves: (none)")

            print()
            continue

        world.remember_action(player_input)
        event = _capture_event(engine.propose_event(world, player_input=player_input))


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Text Adventure prototype")
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=Path("sessions"),
        help="Directory used to store saved sessions (default: ./sessions).",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        help="Session identifier to load on startup if it exists.",
    )
    parser.add_argument(
        "--no-persistence",
        action="store_true",
        help="Disable session persistence commands for this run.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help=(
            "Path to a transcript log capturing narration, metadata, and player input."
        ),
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        help=(
            "Identifier of an LLM provider to add as a secondary agent. "
            "Accepts registered names or module paths (module:factory)."
        ),
    )
    parser.add_argument(
        "--llm-config",
        type=Path,
        help=(
            "Path to a JSON file describing the LLM provider and options. "
            "Cannot be combined with --llm-provider/--llm-option."
        ),
    )
    parser.add_argument(
        "--llm-option",
        dest="llm_options",
        action="append",
        metavar="KEY=VALUE",
        help=(
            "Additional option to pass to the LLM provider factory. "
            "May be supplied multiple times."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Start the scripted demo adventure."""

    args = _parse_args(argv)
    world = WorldState()
    scripted_engine = ScriptedStoryEngine()
    primary_agent = ScriptedStoryAgent("narrator", scripted_engine)

    if args.llm_config and args.llm_provider:
        print(
            "Both --llm-config and --llm-provider were supplied. "
            "Please choose one configuration style."
        )
        raise SystemExit(2)

    if args.llm_config and args.llm_options:
        print(
            "--llm-option cannot be combined with --llm-config. "
            "Encode additional options within the JSON file."
        )
        raise SystemExit(2)

    if args.llm_options and not args.llm_provider:
        print(
            "--llm-option was provided but no --llm-provider was specified. "
            "The adventure cannot start with LLM options alone."
        )
        raise SystemExit(2)

    secondary_agents: list[LLMStoryAgent] = []
    if args.llm_provider or args.llm_config:
        registry = LLMProviderRegistry()
        register_builtin_providers(registry)
        try:
            if args.llm_config:
                llm_client = registry.create_from_config_file(args.llm_config)
            else:
                option_strings: Sequence[str] | None
                if args.llm_options is None:
                    option_strings = None
                else:
                    option_strings = tuple(args.llm_options)
                llm_client = registry.create_from_cli(
                    args.llm_provider,
                    option_strings,
                )
        except Exception as exc:
            identifier = (
                str(args.llm_config)
                if args.llm_config is not None
                else args.llm_provider
            )
            print(f"Failed to initialise LLM provider '{identifier}': {exc}")
            raise SystemExit(2) from exc

        secondary_agents.append(LLMStoryAgent(name="oracle", llm_client=llm_client))

    coordinator = MultiAgentCoordinator(
        primary_agent,
        secondary_agents=secondary_agents,
    )
    engine: StoryEngine = coordinator

    session_store: SessionStore | None = None
    autoload_session: str | None = None
    if not args.no_persistence:
        session_store = FileSessionStore(args.session_dir)
        autoload_session = args.session_id
    elif args.session_id:
        print(
            "--session-id was provided but persistence is disabled. "
            "The adventure will start fresh."
        )

    transcript_logger: TranscriptLogger | None = None
    log_handle: TextIO | None = None
    try:
        if args.log_file is not None:
            args.log_file.parent.mkdir(parents=True, exist_ok=True)
            log_handle = args.log_file.open("a", encoding="utf-8")
            transcript_logger = TranscriptLogger(log_handle)

        run_cli(
            engine,
            world,
            session_store=session_store,
            autoload_session=autoload_session,
            transcript_logger=transcript_logger,
        )
    finally:
        if log_handle is not None:
            log_handle.close()


if __name__ == "__main__":
    main()
