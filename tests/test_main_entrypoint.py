"""Tests covering the CLI entry point and provider selection flags."""

from __future__ import annotations

import builtins
import sys
from textwrap import dedent

import pytest

from main import main


def test_main_supports_llm_provider_selection(tmp_path, monkeypatch, capsys) -> None:
    """Providing an LLM provider should wire it into the coordinator."""

    module_path = tmp_path / "dummy_llm_provider.py"
    module_path.write_text(
        dedent(
            """
            import json

            from textadventure.llm import LLMClient, LLMMessage, LLMResponse


            class DummyLLMClient(LLMClient):
                def __init__(self, narration: str = "oracle", note: str = "") -> None:
                    self.narration = narration
                    self.note = note

                def complete(self, messages, *, temperature=None):
                    payload = {"narration": self.narration}
                    if self.note:
                        payload["metadata"] = {"note": self.note}
                    response = json.dumps(payload)
                    return LLMResponse(
                        LLMMessage(role="assistant", content=response),
                        metadata={"provider": "dummy"},
                    )


            def build_client(**options):
                return DummyLLMClient(**options)
            """
        )
    )

    monkeypatch.syspath_prepend(str(tmp_path))

    inputs = iter(["quit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))

    try:
        main(
            [
                "--llm-provider",
                "dummy_llm_provider:build_client",
                "--llm-option",
                "narration=LLM-guidance",
                "--llm-option",
                "note=clue",
                "--no-persistence",
            ]
        )
    finally:
        sys.modules.pop("dummy_llm_provider", None)

    output = capsys.readouterr().out
    assert "LLM-guidance" in output
    assert "Thanks for playing!" in output


def test_main_rejects_options_without_provider(monkeypatch, capsys) -> None:
    """Supplying provider options without a provider should exit early."""

    with pytest.raises(SystemExit) as excinfo:
        main(["--llm-option", "note=clue", "--no-persistence"])

    assert excinfo.value.code == 2
    error_output = capsys.readouterr().out
    assert "--llm-option was provided" in error_output
