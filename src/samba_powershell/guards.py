"""What a read refuses once it has the object in hand."""

from __future__ import annotations

from collections.abc import Mapping

from samba_powershell.attributes import values_of
from samba_powershell.errors import BackendError
from samba_powershell.object_classes import ClassSpec


# Refuses an object of another class the way Windows does, by not finding it,
# including a derived class the spec excludes: computer inherits from user, yet
# Get-ADUser leaves computers to Get-ADComputer. Every read fetches objectClass, so
# an answer without it is an entry the caller may not read, whatever the cmdlet.
def class_guard(spec: ClassSpec, attributes: Mapping[str, object], identity: str) -> None:
    held = {item.lower() for item in values_of(attributes, "objectClass")
            if isinstance(item, str)}
    if not held:
        raise not_found(identity)
    if not spec.object_class:
        return
    if spec.object_class in held and not held.intersection(spec.excluded):
        return
    raise not_found(identity)


# The one not-found every path reports, in the wording Windows uses, whether
# nothing matched or something of another class did.
def not_found(identity: str) -> BackendError:
    return BackendError(f"Cannot find an object with identity '{identity}'.",
                        "SambaAD.ObjectNotFound", "ObjectNotFound", identity)
