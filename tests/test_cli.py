"""Smoke tests for the command-line interface loop."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from io import StringIO
from pathlib import Path
import json
import os

import builtins

import main
from main import (
    EditorLaunchError,
    EditorLauncher,
    SceneDatasetMonitor,
    TranscriptLogger,
    _TabCompletionManager,
    run_cli,
)
from textadventure import (
    InMemorySessionStore,
    SessionSnapshot,
    SessionStore,
    WorldState,
)
from textadventure.multi_agent import (
    Agent,
    AgentTrigger,
    AgentTurnResult,
    MultiAgentCoordinator,
)
from textadventure.scripted_story_engine import (
    ScriptedStoryEngine,
    load_scenes_from_file,
)
from textadventure.story_engine import StoryChoice, StoryEngine, StoryEvent

import pytest


def _force_mtime_advance(path: Path) -> None:
    """Ensure ``path`` has a strictly newer modification timestamp."""

    current = path.stat().st_mtime_ns
    last = getattr(_force_mtime_advance, "_last", 0)
    target = max(current, last + 1)
    os.utime(path, ns=(target, target))
    _force_mtime_advance._last = target  # type: ignore[attr-defined]


def _write_scene_dataset(path: Path, *, description: str) -> None:
    """Persist a minimal scene dataset for testing watchers."""

    payload = {
        "starting-area": {
            "description": description,
            "choices": [
                {"command": "wait", "description": "Wait for a while."},
            ],
            "transitions": {
                "wait": {"narration": "Time drifts by."},
            },
        }
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _force_mtime_advance(path)


class _IteratorInput:
    """Callable helper that returns successive values from an iterator."""

    def __init__(self, values: Iterator[str]) -> None:
        self._values = values

    def __call__(self, prompt: str = "") -> str:  # pragma: no cover - trivial wrapper
        del prompt
        return next(self._values)


class _FakeReadline:
    """Minimal readline-compatible stub for exercising tab completion logic."""

    def __init__(self) -> None:
        self._completer: Callable[[str, int], str | None] | None = None
        self._delims = " \t\n"
        self._line_buffer = ""
        self._begidx = 0
        self._endidx = 0
        self.bindings: list[str] = []

    def parse_and_bind(self, command: str) -> None:
        self.bindings.append(command)

    def set_completer(self, completer: Callable[[str, int], str | None] | None) -> None:
        self._completer = completer

    def get_completer(self) -> Callable[[str, int], str | None] | None:
        return self._completer

    def set_completer_delims(self, delims: str) -> None:
        self._delims = delims

    def get_completer_delims(self) -> str:
        return self._delims

    def get_line_buffer(self) -> str:
        return self._line_buffer

    def get_begidx(self) -> int:
        return self._begidx

    def get_endidx(self) -> int:
        return self._endidx

    def set_state(self, buffer: str, begidx: int, endidx: int) -> None:
        self._line_buffer = buffer
        self._begidx = begidx
        self._endidx = endidx


def _gather_completions(readline: _FakeReadline, text: str) -> list[str]:
    completer = readline.get_completer()
    assert completer is not None

    results: list[str] = []
    for index in range(20):
        candidate = completer(text, index)
        if candidate is None:
            break
        results.append(candidate)
    return results


class _EndingEngine(StoryEngine):
    """Story engine that immediately returns a terminal event."""

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str]] = []

    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        self.calls.append((player_input, world_state.location))
        return StoryEvent(narration="The adventure ends before it begins.")


class _SequencedAgent(Agent):
    """Agent that replays a scripted sequence of turn results."""

    def __init__(self, name: str, results: Sequence[AgentTurnResult]) -> None:
        self.name = name
        self._results = list(results)

    def propose_event(
        self,
        world_state: WorldState,
        *,
        trigger: AgentTrigger,
    ) -> AgentTurnResult:
        del world_state, trigger
        if not self._results:
            raise AssertionError(
                f"no scripted result available for agent {self.name!r}"
            )
        return self._results.pop(0)


class _StubEditorLauncher(EditorLauncher):
    """Test double that tracks editor lifecycle commands without spawning processes."""

    def __init__(self) -> None:
        super().__init__(host="127.0.0.1", port=8123)
        self.started = 0
        self.stopped = 0
        self._running = False

    def is_running(self) -> bool:  # pragma: no cover - trivial override
        return self._running

    def start(self) -> None:
        if self._running:
            raise EditorLaunchError("already running")
        self._running = True
        self.started += 1

    def stop(self) -> bool:
        if not self._running:
            return False
        self._running = False
        self.stopped += 1
        return True


def test_editor_launcher_start_applies_env_and_reload(monkeypatch) -> None:
    """Launching the editor should honour reload mode and env overrides."""

    recorded: dict[str, object] = {}

    class _FakeProcess:
        def poll(self) -> int | None:
            return None

        def wait(
            self, timeout: float | None = None
        ) -> int:  # pragma: no cover - simple
            del timeout
            return 0

        def terminate(self) -> None:  # pragma: no cover - simple helper
            return None

        def kill(self) -> None:  # pragma: no cover - simple helper
            return None

    def fake_popen(command: Sequence[str], *, env: dict[str, str]) -> _FakeProcess:
        recorded["command"] = list(command)
        recorded["env"] = env
        return _FakeProcess()

    monkeypatch.setattr("main.subprocess.Popen", fake_popen)
    monkeypatch.setattr("main.time.sleep", lambda _: None)

    launcher = EditorLauncher(
        host="127.0.0.1",
        port=9100,
        reload=True,
        env={"TEXTADVENTURE_SCENE_PATH": "/tmp/demo.json"},
    )
    launcher.start()

    command = recorded.get("command")
    assert isinstance(command, list)
    assert "--reload" in command

    env = recorded.get("env")
    assert isinstance(env, dict)
    assert env["TEXTADVENTURE_SCENE_PATH"] == "/tmp/demo.json"

    assert launcher.stop() is True


def test_run_cli_handles_basic_command_sequence(monkeypatch, capsys) -> None:
    """Verify that the CLI processes commands and updates memory."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["look", "inventory", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    captured = capsys.readouterr().out
    assert "Welcome to the Text Adventure prototype!" in captured
    assert "Sunlight filters through tall trees" in captured
    assert "You pause and listen to the rustling leaves." in captured
    assert "You pat your pockets but find nothing of note." in captured
    assert "Thanks for playing!" in captured

    assert world.recent_actions() == ("look", "inventory")
    assert world.location == "starting-area"


def test_run_cli_stops_when_event_has_no_choices(monkeypatch, capsys) -> None:
    """Ensure the loop exits when the story engine provides no choices."""

    engine = _EndingEngine()
    world = WorldState()

    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt="": pytest.fail("input should not be requested"),
    )

    run_cli(engine, world)

    captured = capsys.readouterr().out
    assert "The adventure ends before it begins." in captured
    assert "The story has reached a natural stopping point." in captured

    assert engine.calls == [(None, "starting-area")]
    assert world.recent_actions() == ()


def test_run_cli_supports_saving_and_loading(monkeypatch, capsys) -> None:
    """Ensure the CLI can persist and restore sessions through commands."""

    engine = ScriptedStoryEngine()
    world = WorldState()
    store = InMemorySessionStore()

    inputs = iter(["save demo", "explore", "save demo", "load demo", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world, session_store=store)

    captured = capsys.readouterr().out
    assert "Saved session 'demo'." in captured
    assert "Loaded session 'demo'." in captured

    snapshot = store.load("demo")
    assert snapshot.world_state.location == "old-gate"
    assert world.location == "old-gate"
    assert world.recent_actions() == ("explore",)


def test_run_cli_informs_when_saving_unavailable(monkeypatch, capsys) -> None:
    """Saving without a configured session store should produce guidance."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["save test", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    captured = capsys.readouterr().out
    assert "Saving is unavailable" in captured
    assert "Saved session" not in captured
    assert world.recent_actions() == ()


def test_tutorial_command_walks_through_steps(monkeypatch, capsys) -> None:
    """The tutorial command should provide an interactive walkthrough."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["tutorial", "", "", "", "", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    captured = capsys.readouterr().out
    assert "=== Interactive Tutorial ===" in captured
    assert "Step 1 of" in captured
    assert "Use the CLI helpers" in captured
    assert "Remember that 'help' and 'tutorial'" in captured
    assert world.recent_actions() == ()


def test_tutorial_command_mentions_saving_when_available(monkeypatch, capsys) -> None:
    """When persistence is enabled, the tutorial should highlight save/load."""

    engine = ScriptedStoryEngine()
    world = WorldState()
    store = InMemorySessionStore()

    inputs = iter(["tutorial", "", "", "", "", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world, session_store=store)

    captured = capsys.readouterr().out
    assert "Save your progress at any time" in captured
    assert "also appear in the 'status' command." in captured
    assert world.recent_actions() == ()


def test_run_cli_autoloads_session(monkeypatch, capsys) -> None:
    """Providing autoload details should restore the world before the loop."""

    engine = ScriptedStoryEngine()
    world = WorldState()
    store = InMemorySessionStore()

    world.move_to("old-gate")
    world.remember_action("explore")
    snapshot = SessionSnapshot.capture(world)
    store.save("resume", snapshot)

    # Reset world to confirm autoload applies snapshot
    world = WorldState()

    inputs = iter(["quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world, session_store=store, autoload_session="resume")

    captured = capsys.readouterr().out
    assert "Loaded session 'resume'." in captured
    assert world.location == "old-gate"
    assert world.recent_actions() == ("explore",)


def test_status_command_reports_world_and_queue_details(monkeypatch, capsys) -> None:
    """The debug status command should expose inventory, queue, and saves."""

    world = WorldState()
    world.add_item("lantern")

    store = InMemorySessionStore()
    store.save("checkpoint", SessionSnapshot.capture(world))

    primary_results = (
        AgentTurnResult(
            event=StoryEvent(
                narration="Primary opens the scene.",
                choices=(StoryChoice("wait", "Wait for a moment."),),
            ),
            messages=(
                AgentTrigger(
                    kind="alert",
                    metadata={"target": "scout", "note": "prepare"},
                ),
            ),
        ),
        AgentTurnResult(
            event=StoryEvent(
                narration="Primary continues the tale.",
                choices=(StoryChoice("wait", "Wait for a moment."),),
            ),
        ),
    )

    scout_results = (
        AgentTurnResult(event=StoryEvent("Scout echoes the call.")),
        AgentTurnResult(event=StoryEvent("Scout follows up.")),
    )

    coordinator = MultiAgentCoordinator(
        _SequencedAgent("narrator", primary_results),
        secondary_agents=[_SequencedAgent("scout", scout_results)],
    )

    inputs = iter(["status", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(coordinator, world, session_store=store)

    captured = capsys.readouterr().out
    assert "=== Adventure Status ===" in captured
    assert "Location: starting-area" in captured
    assert "Inventory: lantern" in captured
    assert "Queued agent messages:" in captured
    assert (
        "from narrator (kind=alert, metadata={note=prepare, target=scout})" in captured
    )
    assert "Pending saves: checkpoint" in captured


def test_help_command_offers_contextual_guidance(monkeypatch, capsys) -> None:
    """The help command should surface both general and targeted guidance."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["help", "help explore", "help save", "help unknown", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    output = capsys.readouterr().out
    assert "=== Help ===" in output
    assert "Story choices:" in output
    assert "explore - Head toward the mossy gate." in output
    assert (
        "save <session-id> - Unavailable: session persistence is disabled for this session."
        in output
    )
    assert "=== Help: explore ===" in output
    assert "This choice is currently available: Head toward the mossy gate." in output
    assert "=== Help: save <session-id> ===" in output
    assert "Unavailable: session persistence is disabled for this session." in output
    assert (
        "No help is available for 'unknown'. Showing general guidance instead."
        in output
    )
    assert "Keyboard shortcuts:" in output


def test_run_cli_supports_common_shortcuts(monkeypatch, capsys) -> None:
    """Single-character shortcuts should map to the corresponding commands."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["?", "s", "q"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    output = capsys.readouterr().out
    assert "=== Help ===" in output
    assert "=== Adventure Status ===" in output
    assert "Thanks for playing!" in output


def test_tab_completion_cycles_commands_and_choices() -> None:
    """Readline tab completion should surface commands, choices, and editor actions."""

    readline = _FakeReadline()

    def previous(text: str, state: int) -> str | None:
        del text, state
        return "noop"

    readline.set_completer(previous)
    readline.set_completer_delims("abc")

    manager = _TabCompletionManager(readline)
    manager.update(
        choice_commands=("explore", "wait"),
        system_commands=("help", "status", "quit", "exit"),
        help_topics=("help", "status", "quit", "exit", "explore"),
        editor_actions=("start", "stop", "status"),
    )

    assert readline.bindings == ["tab: complete"]
    active_completer = readline.get_completer()
    assert active_completer is not None
    assert active_completer is not previous

    readline.set_state("", 0, 0)
    assert _gather_completions(readline, "") == [
        "help",
        "status",
        "quit",
        "exit",
        "explore",
        "wait",
    ]

    readline.set_state("help ", 5, 5)
    assert _gather_completions(readline, "") == [
        "help",
        "status",
        "quit",
        "exit",
        "explore",
    ]

    readline.set_state("help st", 5, 7)
    assert _gather_completions(readline, "st") == ["status"]

    readline.set_state("editor ", 7, 7)
    assert _gather_completions(readline, "") == ["start", "stop", "status"]

    manager.close()
    assert readline.get_completer() is previous
    assert readline.get_completer_delims() == "abc"


def test_tab_completion_deduplicates_case_insensitively() -> None:
    """Duplicate commands should collapse regardless of their casing."""

    readline = _FakeReadline()
    manager = _TabCompletionManager(readline)
    manager.update(
        choice_commands=("Look", "look"),
        system_commands=("help", "Quit", "quit"),
        help_topics=("Quit", "quit", "Look", "look"),
        editor_actions=(),
    )

    readline.set_state("", 0, 0)
    assert _gather_completions(readline, "") == ["help", "Quit", "Look"]

    readline.set_state("help ", 5, 5)
    assert _gather_completions(readline, "") == ["Quit", "Look"]

    manager.close()
    assert readline.get_completer() is None


def test_transcript_logger_captures_inputs_and_events(monkeypatch) -> None:
    """A transcript logger should record narration, metadata, and inputs."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["look", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    buffer = StringIO()
    logger = TranscriptLogger(buffer)

    run_cli(engine, world, transcript_logger=logger)

    log = buffer.getvalue()
    assert "=== Turn 1 ===" in log
    assert "Narration:" in log
    assert "Metadata: (none)" in log
    assert "Player input: look" in log
    assert "Player input: quit" in log


def test_scene_dataset_monitor_reloads_updated_file(tmp_path: Path) -> None:
    """Changing the dataset file should refresh the scripted engine."""

    dataset = tmp_path / "scenes.json"
    _write_scene_dataset(dataset, description="Forest canopy glitters.")
    scenes = load_scenes_from_file(dataset)
    engine = ScriptedStoryEngine(scenes=scenes)
    monitor = SceneDatasetMonitor(
        dataset,
        engine,
        initial_timestamp=dataset.stat().st_mtime_ns,
    )

    world = WorldState()
    initial_event = engine.propose_event(world)
    assert "Forest canopy glitters." in initial_event.narration

    _write_scene_dataset(dataset, description="Moonlight bathes the grove.")
    outcome = monitor.poll()
    assert outcome.reloaded
    assert outcome.message and "Reloaded scenes" in outcome.message

    refreshed_event = engine.propose_event(world)
    assert "Moonlight bathes the grove." in refreshed_event.narration


def test_scene_dataset_monitor_reports_errors_once(tmp_path: Path) -> None:
    """Dataset load errors should emit a single notification until resolved."""

    dataset = tmp_path / "scenes.json"
    _write_scene_dataset(dataset, description="River murmurs softly.")
    scenes = load_scenes_from_file(dataset)
    engine = ScriptedStoryEngine(scenes=scenes)
    monitor = SceneDatasetMonitor(
        dataset,
        engine,
        initial_timestamp=dataset.stat().st_mtime_ns,
    )

    dataset.write_text('{\n  "broken": true', encoding="utf-8")
    _force_mtime_advance(dataset)

    first = monitor.poll()
    assert not first.reloaded
    assert first.message and "Failed to reload scenes" in first.message

    second = monitor.poll()
    assert not second.reloaded
    assert second.message is None

    _write_scene_dataset(dataset, description="River path opens ahead.")
    recovered = monitor.poll()
    assert recovered.reloaded
    assert recovered.message and "Reloaded scenes" in recovered.message

    event = engine.propose_event(WorldState())
    assert "River path opens ahead." in event.narration


def test_run_cli_reloads_scene_dataset(monkeypatch, capsys, tmp_path: Path) -> None:
    """The CLI should announce and apply dataset changes between turns."""

    dataset = tmp_path / "scenes.json"
    _write_scene_dataset(dataset, description="Stars glimmer above the trail.")
    scenes = load_scenes_from_file(dataset)
    engine = ScriptedStoryEngine(scenes=scenes)
    monitor = SceneDatasetMonitor(
        dataset,
        engine,
        initial_timestamp=dataset.stat().st_mtime_ns,
    )

    world = WorldState()

    def scripted_input(prompt: str = "") -> str:
        if scripted_input.calls == 0:
            scripted_input.calls += 1
            _write_scene_dataset(
                dataset, description="A lantern now lights the ancient path."
            )
            return ""
        return "quit"

    scripted_input.calls = 0  # type: ignore[attr-defined]

    monkeypatch.setattr(builtins, "input", scripted_input)

    run_cli(engine, world, dataset_monitor=monitor)

    output = capsys.readouterr().out
    assert "Stars glimmer above the trail." in output
    assert "A lantern now lights the ancient path." in output
    assert "[scene-watch] Reloaded scenes" in output


def test_cli_walkthrough_matches_golden(monkeypatch, capsys) -> None:
    """The CLI demo walkthrough should match the curated golden transcript."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(
        [
            "camp",
            "search",
            "return",
            "lookout",
            "train",
            "return",
            "explore",
            "inspect",
            "enter",
            "hall",
            "excavate",
            "crypt",
            "glean",
            "return",
            "return",
            "archives",
            "salvage",
            "study",
            "return",
            "stair",
            "ascend",
            "workshop",
            "scavenge",
            "craft",
            "return",
            "observatory",
            "activate",
            "advance",
            "stabilize",
            "quit",
        ]
    )
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world)

    captured = capsys.readouterr().out
    golden_path = (
        Path(__file__).with_name("data").joinpath("golden_cli_walkthrough.txt")
    )
    assert golden_path.is_file(), "Expected golden CLI transcript to be present."
    expected = golden_path.read_text(encoding="utf-8")
    assert captured == expected


def test_editor_command_controls_launcher(monkeypatch, capsys) -> None:
    """The editor command should control the launcher lifecycle."""

    engine = ScriptedStoryEngine()
    world = WorldState()
    launcher = _StubEditorLauncher()

    inputs = iter(
        [
            "editor",
            "editor",
            "editor status",
            "editor stop",
            "editor stop",
            "quit",
        ]
    )
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world, editor_launcher=launcher)

    captured = capsys.readouterr().out
    assert "Editor is running at http://127.0.0.1:8123" in captured
    assert "Editor is already running" in captured
    assert "Editor status: running at http://127.0.0.1:8123" in captured
    assert "Editor stopped." in captured
    assert "The editor is not currently running." in captured
    assert launcher.started == 1
    assert launcher.stopped == 1


def test_editor_command_handles_disabled_launcher(monkeypatch, capsys) -> None:
    """When the editor is disabled, the CLI should explain the limitation."""

    engine = ScriptedStoryEngine()
    world = WorldState()

    inputs = iter(["editor", "status", "quit"])
    monkeypatch.setattr(builtins, "input", _IteratorInput(inputs))

    run_cli(engine, world, editor_launcher=None)

    captured = capsys.readouterr().out
    assert "Editor integration is unavailable" in captured


def test_main_passes_scene_path_to_editor_launcher(monkeypatch, tmp_path) -> None:
    """Running the CLI with an external scene file shares it with the editor."""

    dataset_path = tmp_path / "scenes.json"
    _write_scene_dataset(dataset_path, description="A quiet grove.")

    captured: dict[str, object] = {}

    class _RecordingLauncher:
        def __init__(
            self,
            *,
            host: str,
            port: int,
            reload: bool = False,
            env: Mapping[str, str] | None = None,
        ) -> None:
            captured["host"] = host
            captured["port"] = port
            captured["reload"] = reload
            captured["env"] = dict(env or {})

        def is_running(self) -> bool:  # pragma: no cover - not exercised
            return False

        def base_url(self) -> str:  # pragma: no cover - not exercised
            return "http://127.0.0.1:8123"

        def start(self) -> None:  # pragma: no cover - not exercised
            return None

        def stop(self) -> bool:  # pragma: no cover - not exercised
            return False

    captured_cli: dict[str, object] = {}

    def fake_run_cli(
        engine: StoryEngine,
        world: WorldState,
        *,
        session_store: SessionStore | None = None,
        autoload_session: str | None = None,
        transcript_logger: TranscriptLogger | None = None,
        editor_launcher: object,
        dataset_monitor: object | None = None,
    ) -> None:
        captured_cli["editor_launcher"] = editor_launcher
        captured_cli["session_store"] = session_store
        captured_cli["autoload_session"] = autoload_session
        captured_cli["transcript_logger"] = transcript_logger
        captured_cli["dataset_monitor"] = dataset_monitor
        return None

    monkeypatch.setattr("main.EditorLauncher", _RecordingLauncher)
    monkeypatch.setattr("main.run_cli", fake_run_cli)

    main.main(
        [
            "--scene-path",
            str(dataset_path),
            "--no-persistence",
            "--editor-reload",
        ]
    )

    assert captured_cli["editor_launcher"].__class__ is _RecordingLauncher
    assert captured["reload"] is True
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["TEXTADVENTURE_SCENE_PATH"] == str(dataset_path.resolve())
