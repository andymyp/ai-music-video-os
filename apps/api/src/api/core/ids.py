"""Entity identifiers (MAD-001 §61, TDD-001 §138-139).

Productions and assets carry globally unique, lexicographically sortable IDs
of the form ``<prefix>_<ULID>``. ULIDs are 128-bit values (48-bit millisecond
timestamp + 80 bits of randomness) encoded in Crockford Base32 (26 chars),
which makes them unique without a database round-trip and naturally ordered by
creation time. Generation happens in the application layer (never inside a
Temporal workflow), so using the wall clock and ``secrets`` here is safe.
"""
from __future__ import annotations

import re
import secrets
import time

# Crockford Base32 alphabet (excludes I, L, O, U).
_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Charset fragment matching a single ULID (26 chars, both cases accepted).
ULID_FRAGMENT = r"[0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{26}"
PRODUCTION_ID_PATTERN = re.compile(rf"^prod_{ULID_FRAGMENT}$")
ASSET_ID_PATTERN = re.compile(rf"^asset_{ULID_FRAGMENT}$")


def _encode_base32(value: int, length: int) -> str:
    """Encode a non-negative integer in Crockford Base32, left-padded to length."""
    chars: list[str] = []
    for _ in range(length):
        value, remainder = divmod(value, 32)
        chars.append(_CROCKFORD_BASE32[remainder])
    return "".join(reversed(chars))


def encode_ulid(timestamp_ms: int, randomness: int) -> str:
    """Encode a 48-bit timestamp and 80-bit randomness as a 26-char ULID."""
    return _encode_base32((timestamp_ms << 80) | randomness, 26)


def new_ulid() -> str:
    """Generate a new random ULID from the current wall-clock time."""
    timestamp_ms = int(time.time() * 1000)
    randomness = int.from_bytes(secrets.token_bytes(10), "big")
    return encode_ulid(timestamp_ms, randomness)


def new_production_id() -> str:
    """Generate a new ``prod_<ULID>`` identifier for a Production."""
    return f"prod_{new_ulid()}"


def new_asset_id() -> str:
    """Generate a new ``asset_<ULID>`` identifier for an Asset."""
    return f"asset_{new_ulid()}"
