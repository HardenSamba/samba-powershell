"""Directory operations exposed through the backend protocol."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import cast

from samba_powershell.client_error import translate_client_error
from samba_powershell.client_loader import ClientFactory
from samba_powershell.errors import BackendError

DEFAULT_USER_PROPERTIES = ("distinguishedName", "name", "sAMAccountName")


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


# Reads the requested property names without accepting ambiguous values.
def requested_properties(parameters: dict[str, object]) -> Sequence[str]:
    value = parameters.get("properties", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BackendError(
            "Parameter 'properties' must be an array of strings.",
            "SambaAD.InvalidParameter",
            "InvalidArgument",
            "properties",
        )
    if not value:
        return DEFAULT_USER_PROPERTIES
    return cast(list[str], value)


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


# Retrieves one user-shaped object through the samba-adws client boundary.
def get_ad_user(
    parameters: dict[str, object],
    client_factory: ClientFactory,
) -> dict[str, object]:
    validate_parameters(parameters)
    identity = required_string(parameters, "identity")
    server = requested_server(parameters)
    properties = requested_properties(parameters)
    try:
        client = client_factory(server, 9389, 30.0)
        result = dict(client.get_by_dn(identity, properties))
    except BackendError:
        raise
    except Exception as exc:
        raise translate_client_error(exc) from exc
    return {"type": "SambaAD.User", "properties": result}
