"""Decoding of the two time encodings Active Directory stores."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from samba_powershell.errors import BackendError

INVALID_VALUE = "SambaAD.InvalidValue"
GENERALIZED_TIME = re.compile(r"(\d{14})(?:\.\d+)?Z")
INTERVAL_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)

# Both sentinels mean "never", not a date near the year 1601 or 30828.
NEVER = frozenset({0, 0x7FFFFFFFFFFFFFFF})


# Reads whenCreated and whenChanged, which carry a generalised time string.
def decode_generalized_time(text: str) -> datetime:
    match = GENERALIZED_TIME.fullmatch(text)
    if match is None:
        raise BackendError(
            f"'{text}' is not a generalised time.",
            INVALID_VALUE,
            "InvalidData",
            text,
        )
    parsed = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    return parsed.replace(tzinfo=timezone.utc)


# Reads a 100-nanosecond interval since 1601, returning None for "never".
def decode_interval_time(value: int) -> datetime | None:
    if value in NEVER:
        return None
    if value < 0:
        raise BackendError(
            f"An interval time cannot be negative, but {value} is.",
            INVALID_VALUE,
            "InvalidData",
        )
    try:
        return INTERVAL_EPOCH + timedelta(microseconds=value // 10)
    except OverflowError as exc:
        raise BackendError(
            f"The interval time {value} falls outside the representable range.",
            INVALID_VALUE,
            "InvalidData",
        ) from exc
