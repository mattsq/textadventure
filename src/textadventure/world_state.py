"""Utilities for tracking the world state of the adventure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Set


@dataclass
class WorldState:
    """Represents the player's current context within the world.

    The world state keeps track of three key pieces of information:

    * ``location`` – the player's current position in the world.
    * ``inventory`` – a collection of unique items currently held by the player.
    * ``history`` – a chronological log of noteworthy events that occurred.

    The helper methods on this class ensure that interactions with the world
    remain validated and that the history reflects only meaningful changes.
    """

    location: str = "starting-area"
    inventory: Set[str] = field(default_factory=set)
    history: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.location = self._validate_label(self.location, "location")

    def move_to(self, location: str, *, record_event: bool = True) -> None:
        """Update the current location of the player.

        Args:
            location: The name of the new location.
            record_event: When ``True`` the transition is captured in the
                history log.

        Raises:
            ValueError: If ``location`` is an empty string.
        """

        validated = self._validate_label(location, "location")
        if validated == self.location:
            return

        self.location = validated
        if record_event:
            self.record_event(f"Moved to {validated}")

    def add_item(self, item: str, *, record_event: bool = True) -> bool:
        """Add an item to the player's inventory.

        Args:
            item: The item identifier to add.
            record_event: When ``True`` the acquisition is logged.

        Returns:
            ``True`` if the item was added to the inventory, ``False`` if it was
            already present.

        Raises:
            ValueError: If ``item`` is empty.
        """

        validated = self._validate_label(item, "item")
        if validated in self.inventory:
            return False

        self.inventory.add(validated)
        if record_event:
            self.record_event(f"Picked up {validated}")
        return True

    def remove_item(self, item: str, *, record_event: bool = True) -> bool:
        """Remove an item from the player's inventory if it exists.

        Args:
            item: The item identifier to remove.
            record_event: When ``True`` the removal is noted in the history.

        Returns:
            ``True`` if the item was removed, ``False`` if it was not present.

        Raises:
            ValueError: If ``item`` is empty.
        """

        validated = self._validate_label(item, "item")
        if validated not in self.inventory:
            return False

        self.inventory.remove(validated)
        if record_event:
            self.record_event(f"Dropped {validated}")
        return True

    def record_event(self, description: str) -> None:
        """Add an event description to the history log."""

        validated = self._validate_label(description, "event description")
        self.history.append(validated)

    def extend_history(self, descriptions: Iterable[str]) -> None:
        """Bulk-add multiple event descriptions to the history."""

        for description in descriptions:
            self.record_event(description)

    @staticmethod
    def _validate_label(value: str, field_name: str) -> str:
        """Strip and validate string values used for world descriptors."""

        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string, got {type(value)!r}")

        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field_name} must be a non-empty string")
        return stripped
