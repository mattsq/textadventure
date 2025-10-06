"""Command-line entry point for the text adventure prototype."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, TextIO, cast

from textadventure import (
    FileSessionStore,
    HIGH_CONTRAST_PALETTE,
    LLMProviderRegistry,
    LLMStoryAgent,
    MultiAgentCoordinator,
    MarkdownPalette,
    ScriptedStoryAgent,
    SessionSnapshot,
    SessionStore,
    StoryEngine,
    StoryEvent,
    WorldState,
    get_markdown_palette,
    set_markdown_palette,
)
from textadventure.llm_providers import register_builtin_providers
from textadventure.scripted_story_engine import (
    ScriptedStoryEngine,
    load_scenes_from_file,
)


class EditorLaunchError(RuntimeError):
    """Raised when the embedded editor server cannot be controlled."""


def _format_host_for_url(host: str) -> str:
    """Return a host suitable for inclusion in an HTTP URL."""

    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


class EditorLauncher:
    """Manage a background ``uvicorn`` process hosting the editor API."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.reload = reload
        self._process: subprocess.Popen[bytes] | None = None
        self._env_overrides = dict(env) if env is not None else None

    def base_url(self) -> str:
        """Return the HTTP URL for the hosted editor."""

        return f"http://{_format_host_for_url(self.host)}:{self.port}"

    def is_running(self) -> bool:
        """Return ``True`` when the editor process is currently active."""

        process = self._process
        if process is None:
            return False
        if process.poll() is not None:
            # The process exited in the background; clear the handle so future
            # launches can succeed cleanly.
            self._process = None
            return False
        return True

    def start(self) -> None:
        """Launch the editor API if it is not already running."""

        if self.is_running():
            raise EditorLaunchError("Editor server is already running.")

        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "textadventure.api.app:create_app",
            "--factory",
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]

        if self.reload:
            command.append("--reload")

        env = os.environ.copy()
        if self._env_overrides is not None:
            env.update(self._env_overrides)

        try:
            process = subprocess.Popen(command, env=env)
        except OSError as exc:  # pragma: no cover - exercising OS failures is hard
            raise EditorLaunchError(f"Failed to launch editor: {exc}") from exc

        # Give the subprocess a brief moment to surface immediate launch
        # failures (for example, when the port is already in use).
        time.sleep(0.2)
        if process.poll() is not None:
            exit_code = process.wait()
            raise EditorLaunchError(
                "Editor server exited immediately. "
                "Check the console output above for details. "
                f"(exit status {exit_code})"
            )

        self._process = process

    def stop(self) -> bool:
        """Terminate the editor process if it is running."""

        process = self._process
        if process is None:
            return False

        self._process = None
        if process.poll() is not None:
            # The process already exited; reap it to avoid zombies.
            process.wait()
            return False

        try:
            process.terminate()
        except OSError as exc:  # pragma: no cover - difficult to simulate
            raise EditorLaunchError(f"Failed to stop editor: {exc}") from exc

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

        return True


class _EditorLauncherSentinel:
    """Sentinel value distinguishing auto-creation from explicit ``None``."""


_EDITOR_LAUNCHER_DEFAULT = _EditorLauncherSentinel()


@dataclass(frozen=True)
class SceneReloadOutcome:
    """Result describing whether the scene dataset changed after polling."""

    reloaded: bool
    message: str | None = None


class SceneDatasetMonitor:
    """Watch a scene dataset on disk and refresh the scripted engine on change."""

    def __init__(
        self,
        path: Path,
        engine: ScriptedStoryEngine,
        *,
        initial_timestamp: int | None = None,
    ) -> None:
        self._path = path
        self._engine = engine
        self._last_timestamp = initial_timestamp
        self._last_error_key: tuple[str, str] | None = None

    def poll(self) -> SceneReloadOutcome:
        """Reload scenes when the dataset file changes or becomes available."""

        try:
            stat = self._path.stat()
        except FileNotFoundError:
            return self._record_error(
                "missing",
                (
                    f"Scene file '{self._path}' is missing. "
                    "Retaining the previously loaded scenes."
                ),
            )
        except OSError as exc:
            return self._record_error(
                "stat",
                (
                    f"Failed to access scene file '{self._path}': {exc}. "
                    "Retaining the previously loaded scenes."
                ),
            )

        timestamp = stat.st_mtime_ns
        needs_reload = (
            self._last_timestamp is None
            or timestamp > self._last_timestamp
            or self._last_error_key is not None
        )
        if not needs_reload:
            return SceneReloadOutcome(reloaded=False)

        try:
            scenes = load_scenes_from_file(self._path)
        except Exception as exc:
            return self._record_error(
                "load",
                (
                    f"Failed to reload scenes from '{self._path}': {exc}. "
                    "Retaining the previously loaded scenes."
                ),
            )

        self._engine.replace_scenes(scenes)
        self._last_timestamp = timestamp
        message = f"Reloaded scenes from '{self._path}'."

        if self._last_error_key is not None:
            message += " Previous load issues have been resolved."
        self._last_error_key = None
        return SceneReloadOutcome(reloaded=True, message=message)

    def _record_error(self, kind: str, message: str) -> SceneReloadOutcome:
        key = (kind, message)
        if self._last_error_key == key:
            return SceneReloadOutcome(reloaded=False)
        self._last_error_key = key
        return SceneReloadOutcome(reloaded=False, message=message)


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


@dataclass(frozen=True)
class TutorialStep:
    """Single step within the interactive tutorial."""

    title: str
    lines: tuple[str, ...]


class TutorialGuide:
    """Guide players through the core CLI features interactively."""

    def __init__(self, session_store: SessionStore | None) -> None:
        self._session_store = session_store

    def run(self) -> None:
        """Render tutorial steps and await confirmation between them."""

        steps = self._build_steps()
        if not steps:
            print("\nTutorial content is not available right now.\n")
            return

        total = len(steps)

        print("\n=== Interactive Tutorial ===")
        print(
            "Type 'next' (or press Enter) to continue, or 'exit' to leave the "
            "tutorial early.\n"
        )

        for index, step in enumerate(steps, start=1):
            print(f"Step {index} of {total}: {step.title}")
            for line in step.lines:
                print(f"  {line}")

            while True:
                try:
                    response = input("tutorial> ")
                except EOFError:
                    print("\nEnding the tutorial because input has closed.\n")
                    return
                except KeyboardInterrupt:
                    print(
                        "\nTutorial interrupted. Resume the adventure whenever "
                        "you're ready.\n"
                    )
                    return

                lowered = response.strip().lower()
                if not lowered or lowered in {"next", "n"}:
                    print()
                    break
                if lowered in {"exit", "quit"}:
                    print(
                        "\nTutorial closed. Use 'help' whenever you need a "
                        "refresher.\n"
                    )
                    return
                if lowered in {"help", "h"}:
                    print(
                        "Type 'next' (or press Enter) to continue, or 'exit' to "
                        "leave the tutorial."
                    )
                    continue

                print(
                    "Type 'next' (or press Enter) to continue, or 'exit' to leave "
                    "the tutorial."
                )

        print(
            "You're ready to explore! Remember that 'help' and 'tutorial' are "
            "always available.\n"
        )

    def _build_steps(self) -> list[TutorialStep]:
        """Return the ordered steps describing core CLI workflows."""

        steps: list[TutorialStep] = [
            TutorialStep(
                title="Read the narration and choices",
                lines=(
                    "Each turn begins with narration describing your surroundings",
                    "and goals.",
                    "Story choices appear as commands in square brackets (for",
                    "example, [explore]). Type the command to follow that branch.",
                ),
            ),
            TutorialStep(
                title="Respond to the narrator",
                lines=(
                    "Enter the command exactly as shown to continue the story.",
                    "If a phrase isn't recognised the scripted engine will nudge",
                    "you back towards the available options.",
                ),
            ),
            TutorialStep(
                title="Use the CLI helpers",
                lines=(
                    "Type 'help' to list every system command or 'help <choice>'",
                    "to learn more about a story option.",
                    "The 'status' command prints your location, inventory, queued",
                    "agent messages, and saved sessions. Use 'quit' to end the",
                    "adventure at any time.",
                ),
            ),
        ]

        if self._session_store is None:
            steps.append(
                TutorialStep(
                    title="Saving progress",
                    lines=(
                        "Saving is disabled for this run because no session",
                        "directory was configured.",
                        "Restart the CLI with '--session-dir <path>' (or without",
                        "'--no-persistence') to enable 'save <name>' and",
                        "'load <name>'.",
                    ),
                )
            )
        else:
            steps.append(
                TutorialStep(
                    title="Saving progress",
                    lines=(
                        "Save your progress at any time with 'save <name>'. Pick",
                        "memorable identifiers like 'camp' or 'chapter-2'.",
                        "Restore a checkpoint with 'load <name>'. Saved sessions",
                        "also appear in the 'status' command.",
                    ),
                )
            )

        return steps


def run_cli(
    engine: StoryEngine,
    world: WorldState,
    *,
    session_store: SessionStore | None = None,
    autoload_session: str | None = None,
    transcript_logger: TranscriptLogger | None = None,
    editor_launcher: (
        EditorLauncher | None | _EditorLauncherSentinel
    ) = _EDITOR_LAUNCHER_DEFAULT,
    dataset_monitor: SceneDatasetMonitor | None = None,
) -> None:
    """Drive a very small interactive loop using ``input``/``print``."""

    if isinstance(editor_launcher, _EditorLauncherSentinel):
        launcher: EditorLauncher | None = EditorLauncher()
    else:
        launcher = cast(EditorLauncher | None, editor_launcher)

    print("Welcome to the Text Adventure prototype!")
    print("Type 'quit' at any time to end the session.")
    print("Type 'help' for a command overview or 'tutorial' for a guided tour.")
    print(
        "Quick shortcuts: 'q' to quit, '?' for help, 's' for status, 't' for the tutorial."
    )
    if session_store is not None:
        print("Type 'save <name>' or 'load <name>' to manage checkpoints.")
    print()

    def _capture_event(new_event: StoryEvent) -> StoryEvent:
        world.remember_observation(new_event.narration)
        if transcript_logger is not None:
            transcript_logger.log_event(new_event)
        return new_event

    event: StoryEvent | None = None

    def _maybe_reload_dataset() -> None:
        nonlocal event

        if dataset_monitor is None:
            return

        outcome = dataset_monitor.poll()
        if outcome.message:
            print(f"\n[scene-watch] {outcome.message}\n")
        if outcome.reloaded:
            event = _capture_event(engine.propose_event(world))

    def _normalise_shortcut(text: str) -> str:
        trimmed = text.strip()
        if not trimmed:
            return trimmed

        lowered = trimmed.lower()
        shortcuts = {
            "q": "quit",
            "h": "help",
            "s": "status",
            "t": "tutorial",
        }

        if trimmed.startswith("?"):
            remainder = trimmed[1:].lstrip()
            return "help" if not remainder else f"help {remainder}"

        if lowered in shortcuts:
            return shortcuts[lowered]

        return trimmed

    def _print_help(topic: str | None) -> None:
        if event is None:
            print("\nHelp is unavailable until the first story event is generated.")
            print()
            return

        command_help: dict[str, tuple[str, str]] = {}
        if session_store is not None:
            command_help["save"] = (
                "save <session-id>",
                "Store your current progress for later.",
            )
            command_help["load"] = (
                "load <session-id>",
                "Restore a previously saved session.",
            )
        else:
            command_help["save"] = (
                "save <session-id>",
                "Unavailable: session persistence is disabled for this session.",
            )
            command_help["load"] = (
                "load <session-id>",
                "Unavailable: session persistence is disabled for this session.",
            )
        command_help["help"] = (
            "help [command]",
            "Display help for available commands. Use 'help <command>' for details.",
        )
        command_help["tutorial"] = (
            "tutorial",
            "Start an interactive walkthrough covering the core CLI commands.",
        )
        command_help["status"] = (
            "status",
            "Show your location, inventory, and queued agent messages.",
        )
        if launcher is None:
            command_help["editor"] = (
                "editor",
                "Unavailable: editor integration is disabled for this session.",
            )
        else:
            command_help["editor"] = (
                "editor [start|stop|status]",
                "Launch or control the browser-based scene editor API.",
            )
        command_help["quit"] = ("quit", "Exit the adventure immediately.")

        choice_map = {choice.command: choice.description for choice in event.choices}

        if topic:
            lowered_topic = topic.lower()
            if lowered_topic in command_help:
                usage, description = command_help[lowered_topic]
                print(f"\n=== Help: {usage} ===")
                print(description)
                print()
                return
            if lowered_topic in choice_map:
                description = choice_map[lowered_topic]
                print(f"\n=== Help: {lowered_topic} ===")
                print(f"This choice is currently available: {description}")
                print("Enter the command exactly as shown to follow this branch.")
                print()
                return
            print(
                f"\nNo help is available for '{topic}'. "
                "Showing general guidance instead."
            )

        print("\n=== Help ===")
        print("Enter one of the story choices below or use a system command.")
        print("Type 'help <command>' to view details about a specific option.")

        print("\nStory choices:")
        if choice_map:
            for command, description in choice_map.items():
                print(f"  {command} - {description}")
        else:
            print("  (No story choices are available right now.)")

        print("\nSystem commands:")
        for usage, description in command_help.values():
            print(f"  {usage} - {description}")

        print("\nKeyboard shortcuts:")
        print("  q - Quit the adventure immediately.")
        print("  ? - Open this help overview.")
        print("  s - Show the adventure status summary.")
        print("  t - Start the interactive tutorial.")
        print()

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
        _maybe_reload_dataset()
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

        player_input = _normalise_shortcut(player_input)

        command, _, argument = player_input.partition(" ")
        command_lower = command.lower()
        lowered = player_input.lower()
        if lowered in {"quit", "exit"}:
            print("\nThanks for playing!")
            break

        if command_lower == "help":
            topic = argument.strip()
            _print_help(topic if topic else None)
            continue

        if command_lower == "tutorial":
            TutorialGuide(session_store).run()
            continue

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

            if launcher is None:
                editor_status = "unavailable (disabled)"
            elif launcher.is_running():
                editor_status = f"running at {launcher.base_url()}"
            else:
                editor_status = "stopped"
            print(f"Editor server: {editor_status}")

            print()
            continue

        if command_lower == "editor":
            if launcher is None:
                print(
                    "\nEditor integration is unavailable for this session. "
                    "Launch the CLI without --no-editor to enable it."
                )
                continue

            action = argument.strip().lower() or "start"
            if action == "start":
                if launcher.is_running():
                    print(f"\nEditor is already running at {launcher.base_url()}")
                else:
                    try:
                        launcher.start()
                    except EditorLaunchError as exc:
                        print(f"\nFailed to start the editor: {exc}")
                    else:
                        print(f"\nEditor is running at {launcher.base_url()}")
                continue
            if action == "stop":
                try:
                    stopped = launcher.stop()
                except EditorLaunchError as exc:
                    print(f"\nFailed to stop the editor: {exc}")
                else:
                    if stopped:
                        print("\nEditor stopped.")
                    else:
                        print("\nThe editor is not currently running.")
                continue
            if action == "status":
                if launcher.is_running():
                    print(f"\nEditor status: running at {launcher.base_url()}")
                else:
                    print("\nEditor status: stopped")
                continue

            print("\nUsage: editor [start|stop|status]")
            print("  start  - Launch the local editor server")
            print("  stop   - Terminate the editor server if it is running")
            print("  status - Display whether the editor server is active")
            continue

        world.remember_action(player_input)
        event = _capture_event(engine.propose_event(world, player_input=player_input))

    if launcher is not None:
        try:
            launcher.stop()
        except EditorLaunchError:
            pass


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
        "--scene-path",
        type=Path,
        help=(
            "Path to a JSON file containing scripted scenes. "
            "Defaults to TEXTADVENTURE_SCENE_PATH when unset."
        ),
    )
    parser.add_argument(
        "--editor-host",
        default="127.0.0.1",
        help="Host interface for the optional editor API server.",
    )
    parser.add_argument(
        "--editor-port",
        type=int,
        default=8000,
        help="Port where the optional editor API server should listen.",
    )
    parser.add_argument(
        "--editor-reload",
        action="store_true",
        help="Run the embedded editor API server with auto-reload enabled.",
    )
    parser.add_argument(
        "--no-editor",
        action="store_true",
        help="Disable the embedded editor command for this session.",
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
    parser.add_argument(
        "--high-contrast",
        action="store_true",
        help=(
            "Render narration and choices with a high-contrast colour palette "
            "suited to low-vision accessibility."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Start the scripted demo adventure."""

    args = _parse_args(argv)
    world = WorldState()
    scene_path: Path | None = args.scene_path
    if scene_path is None:
        env_scene_path = os.getenv("TEXTADVENTURE_SCENE_PATH")
        if env_scene_path is not None:
            trimmed = env_scene_path.strip()
            if trimmed:
                scene_path = Path(trimmed).expanduser()

    dataset_monitor: SceneDatasetMonitor | None = None
    if scene_path is not None:
        try:
            scenes = load_scenes_from_file(scene_path)
        except Exception as exc:
            print(f"Failed to load scenes from '{scene_path}': {exc}")
            raise SystemExit(2) from exc

        try:
            timestamp = scene_path.stat().st_mtime_ns
        except OSError:
            timestamp = None

        scripted_engine = ScriptedStoryEngine(scenes=scenes)
        dataset_monitor = SceneDatasetMonitor(
            scene_path,
            scripted_engine,
            initial_timestamp=timestamp,
        )
        print(
            "Loaded scenes from '{path}'. Changes will reload automatically.".format(
                path=scene_path
            )
        )
    else:
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

    if args.no_editor:
        launcher: EditorLauncher | None = None
    else:
        editor_env: dict[str, str] | None = None
        if scene_path is not None:
            editor_env = {
                "TEXTADVENTURE_SCENE_PATH": str(scene_path.resolve()),
            }
        launcher = EditorLauncher(
            host=args.editor_host,
            port=args.editor_port,
            reload=args.editor_reload,
            env=editor_env,
        )

    transcript_logger: TranscriptLogger | None = None
    log_handle: TextIO | None = None
    previous_palette: MarkdownPalette | None = None
    try:
        if args.high_contrast:
            previous_palette = get_markdown_palette()
            set_markdown_palette(HIGH_CONTRAST_PALETTE)
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
            editor_launcher=launcher,
            dataset_monitor=dataset_monitor,
        )
    finally:
        if previous_palette is not None:
            set_markdown_palette(previous_palette)
        if log_handle is not None:
            log_handle.close()


if __name__ == "__main__":
    main()
