"""Registry for dynamically loading :class:`LLMClient` providers."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Protocol, Sequence

from .llm import LLMClient


class ProviderFactory(Protocol):
    """Protocol describing callables that return :class:`LLMClient` instances."""

    def __call__(self, **options: Any) -> LLMClient:
        """Create a new ``LLMClient`` using keyword arguments as configuration."""


@dataclass(slots=True)
class _ImportedFactory:
    """Lightweight wrapper storing dynamically imported factories."""

    identifier: str
    factory: ProviderFactory


class LLMProviderRegistry:
    """Registry that resolves LLM provider factories by name or import path."""

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderFactory] = {}
        self._dynamic_factories: Dict[str, _ImportedFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        """Register a provider ``factory`` under ``name``.

        Parameters
        ----------
        name:
            Human-friendly identifier used to reference the provider (case-insensitive).
        factory:
            Callable responsible for constructing an :class:`LLMClient`.
        """

        key = _normalise_name(name)
        if key in self._providers:
            raise ValueError(f"Provider '{name}' is already registered")
        if not callable(factory):
            raise TypeError("factory must be callable")
        self._providers[key] = factory

    def available_providers(self) -> Sequence[str]:
        """Return the sorted list of registered provider names."""

        return sorted(self._providers.keys())

    def create(self, identifier: str, **options: Any) -> LLMClient:
        """Instantiate a provider identified by ``identifier``.

        ``identifier`` can either refer to a registered provider name or to a
        Python import path (``module:factory`` or ``module.factory``).
        Additional keyword arguments are forwarded to the provider factory.
        """

        factory = self._resolve_factory(identifier)
        client = factory(**options)
        if not isinstance(client, LLMClient):
            raise TypeError("Provider factory did not return an LLMClient instance")
        return client

    def create_from_config(self, config: Mapping[str, Any] | str) -> LLMClient:
        """Instantiate a provider from configuration mapping or identifier string."""

        if isinstance(config, str):
            identifier = _validate_identifier(config)
            options: Dict[str, Any] = {}
        else:
            if not isinstance(config, Mapping):
                raise TypeError("config must be a mapping or identifier string")
            try:
                provider_value = config["provider"]
            except KeyError as exc:
                raise ValueError("config is missing 'provider'") from exc
            if not isinstance(provider_value, str):
                raise TypeError("config 'provider' must be a string")
            identifier = _validate_identifier(provider_value)
            raw_options = config.get("options", {})
            options = _validate_options_mapping(raw_options)

        return self.create(identifier, **options)

    def create_from_cli(
        self, provider: str, option_strings: Sequence[str] | None = None
    ) -> LLMClient:
        """Instantiate a provider using CLI style ``key=value`` option strings."""

        identifier = _validate_identifier(provider)
        if option_strings is None:
            options: Dict[str, Any] = {}
        else:
            options = parse_cli_options(option_strings)
        return self.create(identifier, **options)

    def _resolve_factory(self, identifier: str) -> ProviderFactory:
        name = _validate_identifier(identifier)
        key = name.lower()
        provider = self._providers.get(key)
        if provider is not None:
            return provider

        if name in self._dynamic_factories:
            return self._dynamic_factories[name].factory

        if ":" not in name and "." not in name:
            raise KeyError(f"No provider registered under '{identifier}'")

        factory = self._import_factory(name)
        self._dynamic_factories[name] = _ImportedFactory(
            identifier=name, factory=factory
        )
        return factory

    def _import_factory(self, identifier: str) -> ProviderFactory:
        module_name, attr_name = _split_identifier(identifier)
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            raise LookupError(
                f"Could not import provider module '{module_name}'"
            ) from exc
        try:
            factory = getattr(module, attr_name)
        except AttributeError as exc:
            raise LookupError(
                f"Factory '{attr_name}' not found in module '{module_name}'"
            ) from exc
        if not callable(factory):
            raise TypeError(
                f"Imported attribute '{attr_name}' from '{module_name}' is not callable"
            )
        return factory  # type: ignore[return-value]


def parse_cli_options(option_strings: Sequence[str]) -> Dict[str, Any]:
    """Parse CLI-style ``key=value`` pairs into a dictionary."""

    options: Dict[str, Any] = {}
    for entry in option_strings:
        if not isinstance(entry, str):
            raise TypeError("CLI option entries must be strings")
        key, sep, raw_value = entry.partition("=")
        if not sep:
            raise ValueError(f"CLI option '{entry}' must be in 'key=value' format")
        key = key.strip()
        if not key:
            raise ValueError("CLI option keys must be non-empty")
        if key in options:
            raise ValueError(f"CLI option '{key}' provided multiple times")
        value = raw_value.strip()
        options[key] = _parse_cli_value(value)
    return options


def _normalise_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("provider name must be a string")
    stripped = name.strip()
    if not stripped:
        raise ValueError("provider name must be non-empty")
    return stripped.lower()


def _validate_identifier(identifier: str) -> str:
    if not isinstance(identifier, str):
        raise TypeError("provider identifier must be a string")
    stripped = identifier.strip()
    if not stripped:
        raise ValueError("provider identifier must be non-empty")
    return stripped


def _split_identifier(identifier: str) -> tuple[str, str]:
    if ":" in identifier:
        module_name, _, attr_name = identifier.partition(":")
    else:
        module_name, _, attr_name = identifier.rpartition(".")
    if not module_name or not attr_name:
        raise ValueError(
            "Dynamic provider identifiers must include a module and attribute"
        )
    return module_name, attr_name


def _validate_options_mapping(
    options: Mapping[str, Any] | MutableMapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(options, Mapping):
        raise TypeError("config 'options' must be a mapping of keyword arguments")
    validated: Dict[str, Any] = {}
    for key, value in options.items():
        if not isinstance(key, str):
            raise TypeError("option keys must be strings")
        validated[key] = value
    return validated


def _parse_cli_value(value: str) -> Any:
    if value == "":
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


__all__ = ["LLMProviderRegistry", "parse_cli_options"]
