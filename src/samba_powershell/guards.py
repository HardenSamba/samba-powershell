"""What a read refuses before and after it touches the wire."""

from __future__ import annotations

from collections.abc import Mapping

from samba_powershell.errors import BackendError
from samba_powershell.identity import classify_identity
from samba_powershell.object_classes import ClassSpec
from samba_powershell.render import find


# The distinguished name a read reaches the wire with. The supported client
# offers get_by_dn only, so a sAMAccountName, SID or GUID cannot be resolved
# yet; saying so beats an enumeration that silently does not happen.
def wire_identity(identity: str) -> str:
    kind = classify_identity(identity)
    if kind != "distinguishedName":
        raise BackendError(
            f"-Identity was given as a {kind} value. Resolving it needs the directory "
            "enumeration the supported samba-adws client does not offer yet; give the "
            "identity as a distinguished name.",
            "SambaAD.IdentityNotResolvable",
            "NotImplemented",
            identity,
        )
    return identity


# Refuses an object of another class the way Windows reports it: the cmdlet
# does not find it, rather than finding it and complaining about its type.
def class_guard(spec: ClassSpec, attributes: Mapping[str, object], identity: str) -> None:
    if not spec.object_class:
        return
    value = find(attributes, "objectClass")
    listed = value if isinstance(value, tuple) else (value,)
    held = {item.lower() for item in listed if isinstance(item, str)}
    if spec.object_class not in held:
        raise BackendError(
            f"Cannot find an object of class '{spec.object_class}' with identity "
            f"'{identity}'.",
            "SambaAD.ObjectNotFound",
            "ObjectNotFound",
            identity,
        )
