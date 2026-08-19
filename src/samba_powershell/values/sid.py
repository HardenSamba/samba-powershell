"""Decoding of the binary objectSid into its textual form."""

from __future__ import annotations

from samba_powershell.errors import BackendError

INVALID_VALUE = "SambaAD.InvalidValue"
HEADER_LENGTH = 8
SUBAUTHORITY_LENGTH = 4
DECIMAL_AUTHORITY_LIMIT = 1 << 32


# Renders one SID as S-1-<authority>-<subauthorities>, per MS-DTYP.
def decode_sid(raw: bytes) -> str:
    revision, count, authority = read_header(raw)
    expected = HEADER_LENGTH + SUBAUTHORITY_LENGTH * count
    if len(raw) < expected:
        raise BackendError(
            f"An objectSid of {len(raw)} bytes cannot hold {count} subauthorities.",
            INVALID_VALUE,
            "InvalidData",
        )
    parts = [str(read_subauthority(raw, index)) for index in range(count)]
    return "-".join(["S", str(revision), format_authority(authority), *parts])


# Reads the revision, the subauthority count and the identifier authority.
def read_header(raw: bytes) -> tuple[int, int, int]:
    if len(raw) < HEADER_LENGTH:
        raise BackendError(
            f"An objectSid needs at least {HEADER_LENGTH} bytes, not {len(raw)}.",
            INVALID_VALUE,
            "InvalidData",
        )
    return raw[0], raw[1], int.from_bytes(raw[2:HEADER_LENGTH], "big")


# Reads one little-endian subauthority by position.
def read_subauthority(raw: bytes, index: int) -> int:
    start = HEADER_LENGTH + SUBAUTHORITY_LENGTH * index
    return int.from_bytes(raw[start : start + SUBAUTHORITY_LENGTH], "little")


# Renders the identifier authority, which is hexadecimal once it exceeds 2^32.
def format_authority(authority: int) -> str:
    if authority < DECIMAL_AUTHORITY_LIMIT:
        return str(authority)
    return f"0x{authority:012x}"
