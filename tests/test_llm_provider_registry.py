"""Tests for the LLM provider registry utilities."""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any, Sequence

import pytest

from textadventure.llm import LLMClient, LLMMessage, LLMResponse
from textadventure.llm_provider_registry import LLMProviderRegistry, parse_cli_options


class DummyClient(LLMClient):
    def __init__(self, **config: Any) -> None:
        self.config = config

    def complete(
        self, messages: Sequence[LLMMessage], *, temperature: float | None = None
    ) -> LLMResponse:
        return LLMResponse(LLMMessage(role="assistant", content="dummy"))


@pytest.fixture()
def registry() -> LLMProviderRegistry:
    return LLMProviderRegistry()


def _registered_factory(**options: Any) -> DummyClient:
    return DummyClient(**options)


def test_register_and_create_provider(registry: LLMProviderRegistry) -> None:
    registry.register("dummy", _registered_factory)
    client = registry.create("dummy", api_key="secret")
    assert isinstance(client, DummyClient)
    assert client.config == {"api_key": "secret"}


def test_register_duplicate_name(registry: LLMProviderRegistry) -> None:
    registry.register("dummy", _registered_factory)
    with pytest.raises(ValueError):
        registry.register("DUMMY", _registered_factory)


def test_create_unknown_provider(registry: LLMProviderRegistry) -> None:
    with pytest.raises(KeyError):
        registry.create("unknown")


def test_create_from_config_mapping(registry: LLMProviderRegistry) -> None:
    registry.register("dummy", _registered_factory)
    client = registry.create_from_config(
        {"provider": "dummy", "options": {"temperature": 0.3}}
    )
    assert isinstance(client, DummyClient)
    assert client.config == {"temperature": 0.3}


def test_create_from_config_string(registry: LLMProviderRegistry) -> None:
    registry.register("dummy", _registered_factory)
    client = registry.create_from_config("dummy")
    assert isinstance(client, DummyClient)
    assert client.config == {}


def test_create_from_config_file(tmp_path: Path, registry: LLMProviderRegistry) -> None:
    registry.register("dummy", _registered_factory)
    config_path = tmp_path / "provider.json"
    config_path.write_text(
        json.dumps({"provider": "dummy", "options": {"temperature": 0.7}}),
        encoding="utf-8",
    )

    client = registry.create_from_config_file(config_path)
    assert isinstance(client, DummyClient)
    assert client.config == {"temperature": 0.7}


def test_create_from_config_file_rejects_invalid_json(
    tmp_path: Path, registry: LLMProviderRegistry
) -> None:
    config_path = tmp_path / "provider.json"
    config_path.write_text('{"provider": }', encoding="utf-8")

    with pytest.raises(ValueError):
        registry.create_from_config_file(config_path)


def test_create_from_config_file_requires_mapping(
    tmp_path: Path, registry: LLMProviderRegistry
) -> None:
    config_path = tmp_path / "provider.json"
    config_path.write_text(json.dumps(["dummy"]), encoding="utf-8")

    with pytest.raises(TypeError):
        registry.create_from_config_file(config_path)


def test_create_from_cli_with_options(registry: LLMProviderRegistry) -> None:
    registry.register("dummy", _registered_factory)
    client = registry.create_from_cli("dummy", ["temperature=0.2", "enabled=true"])
    assert isinstance(client, DummyClient)
    assert client.config == {"temperature": 0.2, "enabled": True}


def test_parse_cli_options_rejects_invalid_format() -> None:
    with pytest.raises(ValueError):
        parse_cli_options(["missing_separator"])


def test_dynamic_import_factory(tmp_path: Path, registry: LLMProviderRegistry) -> None:
    module_path = tmp_path / "external_provider.py"
    module_path.write_text(
        """
from textadventure.llm import LLMClient, LLMMessage, LLMResponse


class ImportedClient(LLMClient):
    def __init__(self, label: str) -> None:
        self.label = label

    def complete(self, messages, *, temperature=None):
        return LLMResponse(LLMMessage(role="assistant", content=self.label))


def build_client(**options):
    return ImportedClient(options["label"])
"""
    )

    sys.path.insert(0, str(tmp_path))
    try:
        client = registry.create("external_provider:build_client", label="imported")
        assert client.label == "imported"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("external_provider", None)


def test_dynamic_import_missing_module(registry: LLMProviderRegistry) -> None:
    with pytest.raises(LookupError) as excinfo:
        registry.create("nonexistent.module:build")
    assert "nonexistent.module" in str(excinfo.value)


def test_dynamic_import_missing_factory(
    tmp_path: Path, registry: LLMProviderRegistry
) -> None:
    module_path = tmp_path / "empty_provider.py"
    module_path.write_text("""value = 42""")
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(LookupError) as excinfo:
            registry.create("empty_provider:build")
        assert "build" in str(excinfo.value)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("empty_provider", None)


def test_dynamic_import_non_callable_factory(
    tmp_path: Path, registry: LLMProviderRegistry
) -> None:
    module_path = tmp_path / "invalid_provider.py"
    module_path.write_text("""builder = 123""")
    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(TypeError) as excinfo:
            registry.create("invalid_provider:builder")
        assert "not callable" in str(excinfo.value)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("invalid_provider", None)


def test_factory_must_return_llm_client(registry: LLMProviderRegistry) -> None:
    def build_non_client(**_: Any) -> object:
        return object()

    registry.register("invalid", build_non_client)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        registry.create("invalid")


def test_cli_parser_handles_empty_value() -> None:
    options = parse_cli_options(["note="])
    assert options == {"note": ""}


def test_parse_cli_options_rejects_duplicate_keys() -> None:
    with pytest.raises(ValueError):
        parse_cli_options(["key=1", "key=2"])


def test_create_rejects_blank_identifier(registry: LLMProviderRegistry) -> None:
    with pytest.raises(ValueError):
        registry.create("   ")


def test_config_requires_provider_key(registry: LLMProviderRegistry) -> None:
    with pytest.raises(ValueError):
        registry.create_from_config({"options": {}})


def test_config_rejects_non_mapping_options(registry: LLMProviderRegistry) -> None:
    registry.register("dummy", _registered_factory)
    with pytest.raises(TypeError):
        registry.create_from_config({"provider": "dummy", "options": ["bad"]})
