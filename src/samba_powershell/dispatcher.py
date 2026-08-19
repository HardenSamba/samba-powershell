"""Operation dispatch for requests received from PowerShell."""

from __future__ import annotations

from typing import cast

from samba_powershell.client_loader import ClientFactory, load_client_factory
from samba_powershell.errors import BackendError
from samba_powershell.operations import get_ad_user


# Routes a validated request to its directory operation.
def dispatch(
    request: dict[str, object],
    client_factory: ClientFactory | None = None,
) -> object:
    operation = cast(str, request["operation"])
    parameters = cast(dict[str, object], request["parameters"])
    if operation == "get_ad_user":
        factory = client_factory or load_client_factory()
        return get_ad_user(parameters, factory)
    raise BackendError(
        f"Operation '{operation}' is not supported.",
        "SambaAD.UnsupportedOperation",
        "NotImplemented",
        operation,
    )
