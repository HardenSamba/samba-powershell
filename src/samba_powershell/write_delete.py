"""Deleting objects, and setting a password without exposing it."""

from __future__ import annotations

from samba_powershell import parameters, write_ops, write_requests
from samba_powershell.client_loader import ClientFactory
from samba_powershell.errors import BackendError


# Deletes one object. The removal is irreversible on this Samba version: see
# docs/deletion.md, which the cmdlet's own warning restates to the operator.
def remove_object(request: dict[str, object], client_factory: ClientFactory) -> dict[str, object]:
    identity = write_requests.target_dn(request)
    server = write_requests.requested_server(request)
    write_ops.perform(client_factory, server, "delete", identity)
    return {"type": "SambaAD.WriteResult", "properties": {"DistinguishedName": identity,
                                                          "Action": "delete"}}


# Sets an account's password. The secret arrives inside the request, which
# crosses the process boundary on standard input, so it never appears on a
# command line or in the environment. A policy refusal is kept distinct from a
# generic failure by the client fault it is translated from.
def set_password(request: dict[str, object], client_factory: ClientFactory) -> dict[str, object]:
    identity = write_requests.target_dn(request)
    server = write_requests.requested_server(request)
    secret = request.get("password")
    if not isinstance(secret, str) or not secret:
        raise BackendError(
            "A password operation needs a non-empty password in the request.",
            "SambaAD.InvalidParameter", "InvalidArgument", "password")
    write_ops.perform(client_factory, server, "set_password", identity, secret)
    return {"type": "SambaAD.WriteResult", "properties": {"DistinguishedName": identity,
                                                          "Action": "set_password"}}
