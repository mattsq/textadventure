"""Entry point for the text adventure prototype."""

from __future__ import annotations

from textadventure import StoryEngine, WorldState
from textadventure.scripted_story_engine import ScriptedStoryEngine


def run_cli(engine: StoryEngine, world: WorldState) -> None:
    """Drive a very small interactive loop using ``input``/``print``."""

    print("Welcome to the Text Adventure prototype!")
    print("Type 'quit' at any time to end the session.\n")

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

        lowered = player_input.lower()
        if lowered in {"quit", "exit"}:
            print("\nThanks for playing!")
            break

        world.remember_action(player_input)
        event = engine.propose_event(world, player_input=player_input)
        world.remember_observation(event.narration)


def main() -> None:
    """Start the scripted demo adventure."""

    world = WorldState()
    engine = ScriptedStoryEngine()
    run_cli(engine, world)


if __name__ == "__main__":
    main()
