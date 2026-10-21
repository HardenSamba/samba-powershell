"""Validation of the request parameters every read operation shares."""

from __future__ import annotations

import os

from samba_powershell.errors import BackendError

# The Active Directory Web Services port, [MS-ADDM]; -Server host:port overrides it.
ADWS_PORT = 9389


# Rejects undeclared fields, including credentials that must stay in Kerberos.
def validate_parameters(parameters: dict[str, object]) -> None:
    unsupported = sorted(parameters.keys() - {"identity", "properties", "server"})
    if unsupported:
        name = unsupported[0]
        raise BackendError(
            f"Parameter '{name}' is not supported by this operation.",
            "SambaAD.InvalidParameter",
            "InvalidArgument",
            name,
        )


# Reads one required string parameter, without the whitespace a paste carries.
def required_string(parameters: dict[str, object], name: str) -> str:
    value = parameters.get(name)
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise BackendError(
            f"Parameter '{name}' must be a non-empty string.",
            "SambaAD.InvalidParameter",
            "InvalidArgument",
            name,
        )
    return text


# Resolves the endpoint from the request or the caller's environment. A value
# of only whitespace is no server at all, and host:port names another port, as
# the Windows module accepts.
def requested_endpoint(parameters: dict[str, object]) -> tuple[str, int]:
    value = parameters.get("server", os.environ.get("SAMBA_AD_SERVER", ""))
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise BackendError(
            "No ADWS server was supplied. Use -Server or SAMBA_AD_SERVER.",
            "SambaAD.ServerRequired",
            "InvalidArgument",
            "Server",
        )
    host, separator, port = text.rpartition(":")
    if separator and host and port.isdigit() and 0 < int(port) < 65536:
        return host, int(port)
    return text, ADWS_PORT
