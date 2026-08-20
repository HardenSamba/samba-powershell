"""Tests for the directory value converters."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from samba_powershell.errors import BackendError
from samba_powershell.values import (
    decode_generalized_time,
    decode_guid,
    decode_interval_time,
    decode_sid,
    is_enabled,
)

# S-1-5-21-1004336348-1177238915-682003330-512, the domain administrators.
DOMAIN_ADMINS = bytes(
    [0x01, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x05]
    + [0x15, 0x00, 0x00, 0x00]
    + [0xDC, 0xF4, 0xDC, 0x3B]
    + [0x83, 0x3D, 0x2B, 0x46]
    + [0x82, 0x8B, 0xA6, 0x28]
    + [0x00, 0x02, 0x00, 0x00]
)
BUILTIN = bytes([1, 1, 0, 0, 0, 0, 0, 5, 32, 0, 0, 0])

# 100-nanosecond intervals since 1601, with both "never" sentinels.
INTERVALS = [
    (0, None),
    (0x7FFFFFFFFFFFFFFF, None),
    (133_000_000_000_000_000, datetime(2022, 6, 18, 4, 26, 40, tzinfo=timezone.utc)),
]


# A binary SID renders in the familiar S-1-5-21-... form.
def test_sid_renders_its_textual_form() -> None:
    assert decode_sid(DOMAIN_ADMINS) == (
        "S-1-5-21-1004336348-1177238915-682003330-512"
    )


# A SID with a single subauthority renders without trailing separators.
def test_short_sid_renders() -> None:
    assert decode_sid(BUILTIN) == "S-1-5-32"


# A truncated SID is refused rather than read past its end.
def test_truncated_sid_is_refused() -> None:
    with pytest.raises(BackendError) as raised:
        decode_sid(DOMAIN_ADMINS[:12])
    assert raised.value.error_id == "SambaAD.InvalidValue"


# The first three GUID fields are stored little-endian and swapped back.
def test_guid_fields_are_byte_swapped() -> None:
    raw = bytes(range(16))
    assert decode_guid(raw) == "03020100-0504-0706-0809-0a0b0c0d0e0f"


# A GUID of the wrong length is refused.
def test_short_guid_is_refused() -> None:
    with pytest.raises(BackendError):
        decode_guid(bytes(15))


# Both sentinels mean "never" rather than a date at either end of the range.
@pytest.mark.parametrize(("raw", "expected"), INTERVALS)
def test_interval_time_handles_its_sentinels(
    raw: int,
    expected: datetime | None,
) -> None:
    assert decode_interval_time(raw) == expected


# A generalised time carries an explicit UTC zone once decoded.
def test_generalized_time_is_timezone_aware() -> None:
    decoded = decode_generalized_time("20260819120000.0Z")
    assert decoded == datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


# A generalised time without the fractional part still decodes.
def test_generalized_time_without_fraction() -> None:
    assert decode_generalized_time("20260819120000Z").day == 19


# A malformed time is refused rather than silently misread.
def test_malformed_generalized_time_is_refused() -> None:
    with pytest.raises(BackendError):
        decode_generalized_time("19 August 2026")


# Enabled is the ACCOUNTDISABLE bit read the other way round.
def test_enabled_reads_the_accountdisable_bit() -> None:
    assert is_enabled(0x0200) is True
    assert is_enabled(0x0202) is False
