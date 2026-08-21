"""Operation dispatch for requests received from PowerShell."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from samba_powershell import write_account, write_create, write_delete
from samba_powershell.client_loader import ClientFactory, load_client_factory
from samba_powershell.errors import BackendError
from samba_powershell.operations import (
    get_ad_computer,
    get_ad_group,
    get_ad_object,
    get_ad_user,
)

Operation = Callable[[dict[str, object], ClientFactory], dict[str, object]]

# The read operations, and the write operations that carry no extra flag.
OPERATIONS: dict[str, Operation] = {
    "get_ad_user": get_ad_user,
    "get_ad_computer": get_ad_computer,
    "get_ad_group": get_ad_group,
    "get_ad_object": get_ad_object,
    "new_ad_object": write_create.new_object,
    "set_ad_object": write_create.set_object,
    "rename_ad_object": write_create.rename_object,
    "remove_ad_object": write_delete.remove_object,
    "set_ad_account_password": write_delete.set_password,
    "add_ad_group_member": lambda req, cf: write_account.group_member(req, cf, add=True),
    "remove_ad_group_member": lambda req, cf: write_account.group_member(req, cf, add=False),
    "enable_ad_account": lambda req, cf: write_account.account_enabled(req, cf, enabled=True),
    "disable_ad_account": lambda req, cf: write_account.account_enabled(req, cf, enabled=False),
}


# Routes a validated request to its directory operation.
def dispatch(
    request: dict[str, object],
    client_factory: ClientFactory | None = None,
) -> object:
    operation = cast(str, request["operation"])
    parameters = cast(dict[str, object], request["parameters"])
    handler = OPERATIONS.get(operation)
    if handler is None:
        raise BackendError(
            f"Operation '{operation}' is not supported.",
            "SambaAD.UnsupportedOperation",
            "NotImplemented",
            operation,
        )
    factory = client_factory or load_client_factory()
    return handler(parameters, factory)
