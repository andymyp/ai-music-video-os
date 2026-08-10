"""Provider registry (TDD-001 §35, MAD-001 §52).

The registry maps capabilities to configured providers. Business logic resolves
a capability — ``provider_registry.resolve(capability=Capability.MUSIC)`` — and
never branches on a provider id (MAD-001 §52). Selection by cost mode and
failover *chains* are routing policy implemented by the pipeline layers; this
registry only stores, orders and resolves. :class:`InMemoryProviderRegistry` is
the deterministic development/test implementation (PRD-001 §46 mock mode).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from api.capabilities.base import Capability, ProviderConfig
from api.core.errors import ConfigurationError


class ProviderRegistry(ABC):
    """Abstract contract mapping capabilities to provider instances."""

    @abstractmethod
    def register(self, capability: Capability, provider: Any, config: ProviderConfig) -> None:
        """Register *provider* for *capability* under *config*."""

    @abstractmethod
    def resolve(self, capability: Capability) -> Any:
        """Return the highest-priority enabled provider for *capability*."""

    @abstractmethod
    def resolve_all(self, capability: Capability) -> list[Any]:
        """Return all enabled providers for *capability*, best first (failover order)."""

    @abstractmethod
    def available(self, capability: Capability) -> bool:
        """Return True if at least one enabled provider is registered for *capability*."""

    @abstractmethod
    def configs(self, capability: Capability) -> list[ProviderConfig]:
        """Return all registered configs for *capability* ordered by priority."""


class InMemoryProviderRegistry(ProviderRegistry):
    """Deterministic in-memory registry (development/test, mock mode)."""

    def __init__(self) -> None:
        self._providers: dict[Capability, dict[str, Any]] = {}
        self._configs: dict[Capability, dict[str, ProviderConfig]] = {}

    def register(self, capability: Capability, provider: Any, config: ProviderConfig) -> None:
        if config.capability is not capability:
            raise ConfigurationError(
                f"config for {config.provider_id!r} targets {config.capability.value!r}, "
                f"not {capability.value!r}"
            )
        self._providers.setdefault(capability, {})[config.provider_id] = provider
        self._configs.setdefault(capability, {})[config.provider_id] = config

    def resolve(self, capability: Capability) -> Any:
        for config in self._enabled_configs(capability):
            provider = self._providers.get(capability, {}).get(config.provider_id)
            if provider is not None:
                return provider
        raise ConfigurationError(f"no enabled provider registered for capability: {capability.value}")

    def resolve_all(self, capability: Capability) -> list[Any]:
        return [
            provider
            for config in self._enabled_configs(capability)
            if (provider := self._providers.get(capability, {}).get(config.provider_id)) is not None
        ]

    def available(self, capability: Capability) -> bool:
        return bool(self._enabled_configs(capability))

    def configs(self, capability: Capability) -> list[ProviderConfig]:
        return sorted(
            self._configs.get(capability, {}).values(),
            key=lambda c: (c.priority, c.provider_id),
        )

    # --- internals ----------------------------------------------------------

    def _enabled_configs(self, capability: Capability) -> list[ProviderConfig]:
        return [config for config in self.configs(capability) if config.enabled]
