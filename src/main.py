"""Entry point for the text adventure prototype."""

from textadventure import WorldState


def main() -> None:
    """Start the placeholder game loop."""

    world = WorldState()

    print("Welcome to the Text Adventure prototype!")
    print(f"You are currently at: {world.location}.")
    if world.inventory:
        print(f"Inventory: {', '.join(sorted(world.inventory))}")
    else:
        print("Inventory: (empty)")


if __name__ == "__main__":
    main()
