"""How an -Identity value becomes the reference a read reaches the wire with."""

from __future__ import annotations

from samba_powershell.attributes import find
from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.errors import BackendError
from samba_powershell.guards import not_found
from samba_powershell.identity import (
    CONTROL_CHARACTER,
    EXTENDED_REFERENCE,
    bare_guid,
    classify_identity,
    is_valid_dn,
)
from samba_powershell.ldap_escape import escape_value
from samba_powershell.object_classes import ClassSpec


# The reference one identity reaches the wire with: a SID or GUID as the <SID=>
# or <GUID=> form the directory resolves itself, a distinguished name as it is
# once well formed, and an account name through a search.
def wire_reference(identity: str, spec: ClassSpec, directory: DirectoryClient) -> str:
    refuse_control(identity)
    if EXTENDED_REFERENCE.fullmatch(identity):
        return identity
    kind = classify_identity(identity)
    if kind == "objectSid":
        return f"<SID={identity.upper()}>"
    if kind == "objectGUID":
        return f"<GUID={bare_guid(identity)}>"
    if kind == "distinguishedName":
        return checked_dn(identity)
    return account_reference(identity, spec, directory)


# Refuses an identity holding a control character: none of the forms can, and
# the directory compares only up to a NUL, so a suffix would be silently dropped.
def refuse_control(identity: str) -> None:
    if CONTROL_CHARACTER.search(identity):
        raise BackendError(
            f"Identity {identity!r} contains a control character, which no account name, "
            "GUID, SID or distinguished name holds.",
            "SambaAD.InvalidIdentity", "InvalidArgument", identity)


# Refuses a malformed distinguished name before it travels, naming the value.
def checked_dn(identity: str) -> str:
    if is_valid_dn(identity):
        return identity
    raise BackendError(
        f"'{identity}' is not a valid distinguished name: every component needs an "
        "attribute, an equals sign and a value, as in CN=Jane Doe,CN=Users,DC=example,DC=com.",
        "SambaAD.InvalidIdentity",
        "InvalidArgument",
        identity,
    )


# The distinguished name of the one object an account name belongs to, found
# the way Windows resolves -Identity: a sAMAccountName search of the domain.
def account_reference(identity: str, spec: ClassSpec, directory: DirectoryClient) -> str:
    if not spec.account_names:
        raise BackendError(f"'{identity}' is neither a distinguished name, a GUID nor a SID, "
                           "which is what Get-ADObject takes; use Get-ADUser, Get-ADComputer "
                           "or Get-ADGroup for an account name.",
                           "SambaAD.IdentityNotResolvable", "InvalidArgument", identity)
    base = directory.naming_context("defaultNamingContext")
    found = directory.search(base, "Subtree", account_filter(identity, spec),
                             ("distinguishedName",), 2)
    if not found:
        raise not_found(identity)
    if len(found) > 1:
        raise BackendError(f"The account name '{identity}' matches more than one object of "
                           f"class '{spec.object_class}' under '{base}'.",
                           "SambaAD.IdentityNotUnique", "InvalidResult", identity)
    if isinstance(dn := find(found[0], "distinguishedName"), str):
        return dn
    raise BackendError(f"The directory answered the search for '{identity}' without a "
                       "distinguished name.", "SambaAD.ProtocolError", "ProtocolError", identity)


# The filter an account name implies for this cmdlet's class. A computer's
# sAMAccountName ends in '$', which Windows lets the caller leave out.
def account_filter(identity: str, spec: ClassSpec) -> str:
    value = escape_value(identity)
    names = f"(sAMAccountName={value})"
    if spec.account_suffix and not identity.endswith(spec.account_suffix):
        names = f"(|{names}(sAMAccountName={value}{escape_value(spec.account_suffix)}))"
    refused = "".join(f"(!(objectClass={escape_value(name)}))" for name in spec.excluded)
    return f"(&(objectClass={escape_value(spec.object_class)}){refused}{names})"
