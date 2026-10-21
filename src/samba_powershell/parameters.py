"""Validation of the request parameters every read operation shares."""

from __future__ import annotations

import os

from samba_powershell.errors import BackendError
from samba_powershell.identity import CONTROL_CHARACTER

# The Active Directory Web Services port, [MS-ADDM]; -Server host:port overrides it.
ADWS_PORT = 9389
# What a paste carries around a value: dropped. Python's str.strip() would drop
# more, control characters such as US and FF included, and resolve the rest.
PASTE_WHITESPACE = " \t\r\n"


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


# Reads one required string parameter, without the spaces, tabs and line breaks
# a paste carries. Other control characters stay, for the caller to refuse.
def required_string(parameters: dict[str, object], name: str) -> str:
    value = parameters.get(name)
    text = value.strip(PASTE_WHITESPACE) if isinstance(value, str) else ""
    if not text:
        raise BackendError(
            f"Parameter '{name}' must be a non-empty string.",
            "SambaAD.InvalidParameter",
            "InvalidArgument",
            name,
        )
    return text


# Resolves the endpoint from the request or the caller's environment: the host,
# the port, host:port naming another one as the Windows module accepts, and the
# value as given, which is what a failure reports. Blank is no server at all.
def requested_endpoint(parameters: dict[str, object]) -> tuple[str, int, str]:
    value = parameters.get("server", os.environ.get("SAMBA_AD_SERVER", ""))
    text = value.strip(PASTE_WHITESPACE) if isinstance(value, str) else ""
    if not text:
        raise BackendError(
            "No ADWS server was supplied. Use -Server or SAMBA_AD_SERVER.",
            "SambaAD.ServerRequired",
            "InvalidArgument",
            "Server",
        )
    if CONTROL_CHARACTER.search(text):
        raise BackendError(f"Server {text!r} contains a control character, which no host "
                           "name holds.", "SambaAD.InvalidParameter", "InvalidArgument", text)
    host, separator, port = text.rpartition(":")
    if separator and host and port.isdigit() and 0 < int(port) < 65536:
        return host, int(port), text
    return text, ADWS_PORT, text
