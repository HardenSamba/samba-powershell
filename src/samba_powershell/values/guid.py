"""Decoding of the binary objectGUID into its textual form."""

from __future__ import annotations

import uuid

from samba_powershell.errors import BackendError

GUID_LENGTH = 16


# Renders one objectGUID, whose first three fields are stored little-endian.
def decode_guid(raw: bytes) -> str:
    if len(raw) != GUID_LENGTH:
        raise BackendError(
            f"An objectGUID needs {GUID_LENGTH} bytes, not {len(raw)}.",
            "SambaAD.InvalidValue",
            "InvalidData",
        )
    return str(uuid.UUID(bytes_le=raw))
