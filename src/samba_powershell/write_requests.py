"""Reading the shapes a write request carries, refused when malformed."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from samba_powershell import parameters
from samba_powershell.errors import BackendError
from samba_powershell.guards import wire_identity


# The attribute set a create or modify carries, validated to strings only so a
# password can never be smuggled in as an ordinary attribute.
def attributes_of(request: dict[str, object]) -> Mapping[str, Sequence[str]]:
    value = request.get("attributes", {})
    if not isinstance(value, dict):
        raise BackendError(
            "Parameter 'attributes' must be an object of string lists.",
            "SambaAD.InvalidParameter", "InvalidArgument", "attributes")
    built: dict[str, list[str]] = {}
    for name, values in value.items():
        items = values if isinstance(values, list) else [values]
        built[str(name)] = [str(item) for item in items]
    return built


# The distinguished name a write acts on, refused unless it is a DN.
def target_dn(request: dict[str, object]) -> str:
    return wire_identity(parameters.required_string(request, "identity"))


# The endpoint a write reaches, from the request or the environment.
def requested_server(request: dict[str, object]) -> str:
    return parameters.requested_server(request)
