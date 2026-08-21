"""Membership and account state: reads first, then one idempotent write."""

from __future__ import annotations

from samba_powershell import write_helpers, write_ops, write_requests
from samba_powershell.client_loader import ClientFactory
from samba_powershell.errors import BackendError
from samba_powershell.values.account_control import ACCOUNTDISABLE

MEMBER = "member"
UAC = "userAccountControl"


# The current values of one attribute on an object, read through get_by_dn.
def current(client: object, identity: str, attribute: str) -> list[str]:
    reader = getattr(client, "get_by_dn")
    found = dict(reader(identity, [attribute]))
    value = next((found[key] for key in found if key.lower() == attribute.lower()), ())
    listed = value if isinstance(value, (list, tuple)) else [value]
    return [str(item) for item in listed if item != ""]


# Adds or removes one member, and does nothing when the change is already true:
# adding a present member and removing an absent one are the reruns that decide
# whether a provisioning script is safe to run twice, and both are no-ops here.
def group_member(request: dict[str, object], client_factory: ClientFactory,
                 add: bool) -> dict[str, object]:
    group = write_requests.target_dn(request)
    member = write_helpers.member_dn(request)
    server = write_requests.requested_server(request)
    client = write_ops.writable_client(client_factory, server, "modify")
    present = current(client, group, MEMBER)
    wanted = write_helpers.with_member(present, member, add)
    if write_helpers.same_members(present, wanted):
        return write_helpers.result(group, "member-unchanged")
    write_ops.call_on(client, "modify", group, {MEMBER: wanted})
    return write_helpers.result(group, "add-member" if add else "remove-member")


# Enables or disables an account by flipping one bit of userAccountControl,
# read first so the other flags are preserved rather than overwritten.
def account_enabled(request: dict[str, object], client_factory: ClientFactory,
                    enabled: bool) -> dict[str, object]:
    identity = write_requests.target_dn(request)
    server = write_requests.requested_server(request)
    client = write_ops.writable_client(client_factory, server, "modify")
    values = current(client, identity, UAC)
    if not values or not values[0].lstrip("-").isdigit():
        raise BackendError(f"{identity} has no readable userAccountControl.",
                          "SambaAD.InvalidValue", "InvalidData", identity)
    flags = int(values[0])
    updated = flags & ~ACCOUNTDISABLE if enabled else flags | ACCOUNTDISABLE
    if updated == flags:
        return write_helpers.result(
            identity, "enabled-unchanged" if enabled else "disabled-unchanged")
    write_ops.call_on(client, "modify", identity, {UAC: [str(updated)]})
    return write_helpers.result(identity, "enable" if enabled else "disable")
