"""Operation dispatch for requests received from PowerShell."""

from __future__ import annotations

from typing import cast

from samba_powershell.client_loader import ClientFactory, load_client_factory
from samba_powershell.errors import BackendError
from samba_powershell.object_classes import SPECS
from samba_powershell.operations import get_object

# Each backend operation reads one object of the class its cmdlet returns.
OPERATIONS = {
    "get_ad_user": SPECS["user"],
    "get_ad_computer": SPECS["computer"],
    "get_ad_group": SPECS["group"],
    "get_ad_object": SPECS["object"],
}


# Routes a validated request to its directory operation.
def dispatch(
    request: dict[str, object],
    client_factory: ClientFactory | None = None,
) -> object:
    operation = cast(str, request["operation"])
    parameters = cast(dict[str, object], request["parameters"])
    spec = OPERATIONS.get(operation)
    if spec is None:
        raise BackendError(
            f"Operation '{operation}' is not supported.",
            "SambaAD.UnsupportedOperation",
            "NotImplemented",
            operation,
        )
    factory = client_factory or load_client_factory()
    return get_object(parameters, factory, spec)
