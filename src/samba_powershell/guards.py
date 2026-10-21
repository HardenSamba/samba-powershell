"""What a read refuses once it has the object in hand."""

from __future__ import annotations

from collections.abc import Mapping

from samba_powershell.attributes import values_of
from samba_powershell.errors import BackendError
from samba_powershell.object_classes import ClassSpec


# Refuses an object of another class the way Windows reports it: the cmdlet
# does not find it, rather than finding it and complaining about its type. A
# class derived from the one accepted can still be refused by name, which is
# how Get-ADUser leaves computers to Get-ADComputer although computer inherits
# from user.
def class_guard(spec: ClassSpec, attributes: Mapping[str, object], identity: str) -> None:
    if not spec.object_class:
        return
    held = {item.lower() for item in values_of(attributes, "objectClass")
            if isinstance(item, str)}
    if spec.object_class in held and not held.intersection(spec.excluded):
        return
    raise BackendError(
        f"Cannot find an object of class '{spec.object_class}' with identity "
        f"'{identity}'.",
        "SambaAD.ObjectNotFound",
        "ObjectNotFound",
        identity,
    )
