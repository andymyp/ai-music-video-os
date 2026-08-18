"""Application error taxonomy (MAD-001 §51).

All backend errors derive from :class:`AppError` so a single ``except AppError``
catches every application-level failure while letting unexpected exceptions
bubble up as bugs. Provider adapters raise the *Provider* subclasses; the
domain layer raises :class:`DomainError` subclasses; infrastructure raises the
remaining categories. The names mirror MAD-001 §51; ``TimeoutError`` and
``ValidationError`` intentionally shadow the builtins so callers always catch
the application's own types.
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for all application errors."""


# --- Domain ---------------------------------------------------------------

class DomainError(AppError):
    """Raised when a domain rule is violated (e.g. invalid state transition)."""


class InvalidStateTransitionError(DomainError):
    """Raised when an entity is moved to a status its state machine forbids."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Invalid state transition: {current!r} -> {target!r}")


class ValidationError(DomainError):
    """Raised for application-level validation that Pydantic cannot express."""


# --- Configuration --------------------------------------------------------

class ConfigurationError(AppError):
    """Raised when environment/configuration is invalid or missing."""


# --- Providers ------------------------------------------------------------

class ProviderError(AppError):
    """Base class for provider adapter failures."""


class RateLimitError(ProviderError):
    """Raised when a provider rate-limits a request."""


class AuthenticationError(ProviderError):
    """Raised when a provider rejects the configured credentials."""


class TimeoutError(ProviderError):
    """Raised when a provider request exceeds its timeout."""


# --- Media / storage / workflows ------------------------------------------

class MediaProcessingError(AppError):
    """Raised when FFmpeg/FFprobe or media tooling fails."""


class StorageError(AppError):
    """Raised when a storage operation fails."""


class WorkflowError(AppError):
    """Raised when a Temporal workflow/activity fails unexpectedly."""


class AgentError(AppError):
    """Raised when an agent fails (invalid AI output, missing tool, guardrail)."""


class ToolError(AppError):
    """Raised when a registered tool fails or is unavailable."""


class QualityCheckError(AppError):
    """Raised when a production fails mandatory quality control."""
