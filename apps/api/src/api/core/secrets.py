"""Secret resolution and handling (Phase 23 Security; MAD-001 §48, TDD-001 §79).

Secrets live in environment variables (or an OS credential store in production
desktop builds) — never in source code, configuration, logs, metrics or the
database. ``credentials_reference`` on a :class:`ProviderConfig` is an
*indirection*: this module is the only place a reference is resolved to a value,
and it never logs what it resolves. Real provider adapters obtain credentials at
call time via :func:`resolve_credentials`; agents and the frontend never see
them (TDD-001 §90 security boundary).
"""

from __future__ import annotations

import logging
import os
import re

from api.core.errors import ConfigurationError
from api.core.paths import find_project_root

logger = logging.getLogger("amv.security")

#: A credentials reference is an environment-variable name: uppercase letters,
#: digits and underscores, never starting with a digit. A name can never *be* a
#: secret value (those contain ``-``/``.``/lowercase/paths), so storing one in
#: config is structurally impossible.
_ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def is_valid_reference(reference: str | None) -> bool:
    """True when *reference* is a well-formed env-var name (not a secret/path)."""
    return bool(reference and _ENV_NAME_PATTERN.fullmatch(reference))


def _load_dotenv_values() -> dict[str, str]:
    """Best-effort read of the repo-root ``.env`` file (no side effects)."""
    try:
        from dotenv import dotenv_values  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - optional dependency
        return {}
    env_file = find_project_root() / ".env"
    if not env_file.is_file():
        return {}
    values = dotenv_values(env_file)
    return {key: value for key, value in values.items() if value is not None}


def get_secret(reference: str) -> str | None:
    """Resolve *reference* to its secret value, or ``None`` when unset.

    Precedence: process environment first, then the repo-root ``.env`` file
    (matching the documented workflow in ``.env.example``). An invalid reference
    — a literal secret, a path, lowercase junk — raises ``ConfigurationError``
    instead of resolving silently: a misconfiguration must fail loudly rather
    than expose a value. The resolved value is never logged; the debug line
    names only the reference.
    """
    if not is_valid_reference(reference):
        raise ConfigurationError(
            f"invalid secret reference {reference!r}: must be an env-var name, not a secret value"
        )
    value = os.environ.get(reference)
    if value is None:
        value = _load_dotenv_values().get(reference)
    if value is not None:
        logger.debug("resolved secret reference %s", reference)
    return value


def resolve_credentials(credentials_reference: str | None) -> dict[str, str]:
    """Return ``{reference: secret}`` for a provider call, or ``{}`` when unset.

    This is the boundary real provider adapters call to obtain credentials: the
    secret is handed to the provider for the duration of one call and never
    stored on the config or in any persisted record (TDD-001 §78-79).
    """
    if not credentials_reference:
        return {}
    value = get_secret(credentials_reference)
    return {credentials_reference: value} if value is not None else {}
