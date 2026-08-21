"""Creating objects, and changing the attributes of existing ones."""

from __future__ import annotations

from samba_powershell import parameters, write_ops, write_requests
from samba_powershell.client_loader import ClientFactory


# Creates one object from the attributes the cmdlet assembled, objectClass
# included. A name already in use comes back as the client's own conflict fault,
# translated, so the message names the collision rather than a generic failure.
def new_object(request: dict[str, object], client_factory: ClientFactory) -> dict[str, object]:
    identity = write_requests.target_dn(request)
    server = write_requests.requested_server(request)
    write_ops.perform(client_factory, server, "create", identity,
                      write_requests.attributes_of(request))
    return {"type": "SambaAD.WriteResult", "properties": {"DistinguishedName": identity,
                                                          "Action": "create"}}


# Replaces or clears the attributes named in the request on an existing object.
def set_object(request: dict[str, object], client_factory: ClientFactory) -> dict[str, object]:
    identity = write_requests.target_dn(request)
    server = write_requests.requested_server(request)
    write_ops.perform(client_factory, server, "modify", identity,
                      write_requests.attributes_of(request))
    return {"type": "SambaAD.WriteResult", "properties": {"DistinguishedName": identity,
                                                          "Action": "modify"}}


# Moves or renames one object to a new distinguished name. Both are one LDAP
# modrdn; Move-ADObject changes the parent, Rename-ADObject the leaf, and the
# cmdlet composes the target DN either way.
def rename_object(request: dict[str, object], client_factory: ClientFactory) -> dict[str, object]:
    identity = write_requests.target_dn(request)
    server = write_requests.requested_server(request)
    new_dn = parameters.required_string(request, "new_dn")
    write_ops.perform(client_factory, server, "rename", identity, new_dn)
    return {"type": "SambaAD.WriteResult",
            "properties": {"DistinguishedName": new_dn, "Action": "rename"}}
