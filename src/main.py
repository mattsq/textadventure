"""Command-line entry point for the text adventure prototype."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from textadventure import (
    FileSessionStore,
    MultiAgentCoordinator,
    ScriptedStoryAgent,
    SessionSnapshot,
    SessionStore,
    StoryEngine,
    WorldState,
)
from textadventure.scripted_story_engine import ScriptedStoryEngine


def run_cli(
    engine: StoryEngine,
    world: WorldState,
    *,
    session_store: SessionStore | None = None,
    autoload_session: str | None = None,
) -> None:
    """Drive a very small interactive loop using ``input``/``print``."""

    print("Welcome to the Text Adventure prototype!")
    print("Type 'quit' at any time to end the session.")
    if session_store is not None:
        print("Type 'save <name>' or 'load <name>' to manage checkpoints.\n")
    else:
        print()

    event = None
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
            event = engine.propose_event(world)
            world.remember_observation(event.narration)

    if event is None:
        event = engine.propose_event(world)
        world.remember_observation(event.narration)

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
        if not player_input:
            event = engine.propose_event(world)
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
                print("\nSession persistence is not configured. Loading is unavailable.")
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
                        event = engine.propose_event(world)
                        world.remember_observation(event.narration)
            continue

        world.remember_action(player_input)
        event = engine.propose_event(world, player_input=player_input)
        world.remember_observation(event.narration)


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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Start the scripted demo adventure."""

    args = _parse_args(argv)
    world = WorldState()
    scripted_engine = ScriptedStoryEngine()
    coordinator = MultiAgentCoordinator(
        ScriptedStoryAgent("narrator", scripted_engine)
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

    run_cli(engine, world, session_store=session_store, autoload_session=autoload_session)


if __name__ == "__main__":
    main()
