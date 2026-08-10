"""Workflow runtime configuration (TDD-001 §83-84, MAD-001 §9, §52).

Temporal owns workflow/activity retries; the application must not build a
competing retry engine (TDD-001 §84). This module only *configures* Temporal's
retry policies and exposes a pure classifier (:func:`is_retryable`) that
mirrors MAD-001 §52: transient/provider failures are retried with exponential
backoff, permanent errors (invalid input, bad configuration, authentication,
invalid state) are not.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio.common import RetryPolicy

from api.core.errors import (
    AuthenticationError,
    ConfigurationError,
    InvalidStateTransitionError,
    QualityCheckError,
    ValidationError,
)

#: Exponential backoff cadence (TDD-001 §83: 1s -> 2s -> 4s -> ...).
_INITIAL_INTERVAL = timedelta(seconds=1)
_MAX_INTERVAL = timedelta(seconds=30)
_BACKOFF_COEFFICIENT = 2.0
_MAX_ATTEMPTS = 5

#: Errors that must never be retried (MAD-001 §52 "Not automatically
#: retryable"). Type names must match ``type(exc).__name__`` because Temporal
#: matches ``non_retryable_error_types`` against the failure's class name.
NON_RETRYABLE_TYPES: frozenset[str] = frozenset({
    "ValidationError",
    "ConfigurationError",
    "AuthenticationError",
    "InvalidStateTransitionError",
    "QualityCheckError",
})


def is_retryable(exc: BaseException) -> bool:
    """Classify *exc* for retryability (MAD-001 §52).

    Retryable: temporary provider/infrastructure failures (rate limits,
    timeouts, transient provider errors). Everything else — including
    validation/configuration/auth errors — is treated as permanent.
    """
    from api.core.errors import ProviderError

    if isinstance(exc, ProviderError) and not isinstance(exc, AuthenticationError):
        return True
    return type(exc).__name__ not in NON_RETRYABLE_TYPES


def default_activity_retry_policy() -> RetryPolicy:
    """Exponential-backoff policy for ordinary activities (TDD-001 §83)."""
    return RetryPolicy(
        initial_interval=_INITIAL_INTERVAL,
        backoff_coefficient=_BACKOFF_COEFFICIENT,
        maximum_interval=_MAX_INTERVAL,
        maximum_attempts=_MAX_ATTEMPTS,
        non_retryable_error_types=sorted(NON_RETRYABLE_TYPES),
    )


def provider_retry_policy() -> RetryPolicy:
    """Policy for activities that call external providers.

    Uses the same exponential backoff as :func:`default_activity_retry_policy`
    (TDD-001 §83) but never retries the permanent provider/auth/config errors.
    """
    return default_activity_retry_policy()


@dataclass(frozen=True)
class WorkflowConfig:
    """Task queue + timeout knobs for the production workflow (MAD-001 §9)."""

    task_queue: str = "production"
    workflow_id_prefix: str = "production"
    run_timeout: timedelta = timedelta(hours=24)
    task_timeout: timedelta = timedelta(seconds=10)
    validation_timeout: timedelta = timedelta(seconds=30)
    step_timeout: timedelta = timedelta(minutes=15)
    max_steps_per_run: int = 20
    max_attempts: int = _MAX_ATTEMPTS
    non_retryable_error_types: tuple[str, ...] = field(
        default_factory=lambda: tuple(sorted(NON_RETRYABLE_TYPES))
    )

    def workflow_id(self, production_id: str, attempt: int = 1) -> str:
        """Deterministic Temporal workflow id for a production execution."""
        return f"{self.workflow_id_prefix}-{production_id}-a{attempt}"


def default_workflow_config() -> WorkflowConfig:
    """Return the default workflow configuration."""
    return WorkflowConfig()
