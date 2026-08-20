"""Validation of the request parameters every read operation shares."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import cast

from samba_powershell.errors import BackendError


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


# Reads and validates one required string parameter.
def required_string(parameters: dict[str, object], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value:
        raise BackendError(
            f"Parameter '{name}' must be a non-empty string.",
            "SambaAD.InvalidParameter",
            "InvalidArgument",
            name,
        )
    return value


# Reads the extra property names the caller asked for beyond the default set.
def requested_extras(parameters: dict[str, object]) -> list[str]:
    value = parameters.get("properties", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BackendError(
            "Parameter 'properties' must be an array of strings.",
            "SambaAD.InvalidParameter",
            "InvalidArgument",
            "properties",
        )
    return cast(list[str], value)


# The attribute fetch for one call: the class's default set, plus whatever was
# asked for. -Properties adds to the defaults rather than replacing them, the
# decided contract of docs/cmdlets.md, and LDAP attribute names have no case,
# so a default asked for again in another spelling is not fetched twice.
def fetch_list(defaults: Sequence[str], extras: Sequence[str]) -> tuple[str, ...]:
    merged = {name.lower(): name for name in defaults}
    for name in extras:
        merged.setdefault(name.lower(), name)
    return tuple(merged.values())


# Resolves the endpoint from the request or the caller's environment.
def requested_server(parameters: dict[str, object]) -> str:
    value = parameters.get("server", os.environ.get("SAMBA_AD_SERVER", ""))
    if not isinstance(value, str) or not value:
        raise BackendError(
            "No ADWS server was supplied. Use -Server or SAMBA_AD_SERVER.",
            "SambaAD.ServerRequired",
            "InvalidArgument",
            "Server",
        )
    return value
