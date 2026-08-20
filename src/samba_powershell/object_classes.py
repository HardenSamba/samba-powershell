"""The object classes the read cmdlets know, and what each returns by default."""

from __future__ import annotations

from dataclasses import dataclass


# One cmdlet's shape: its PowerShell type, the objectClass it accepts, and the
# attribute fetch behind the default property set docs/cmdlets.md decides.
# Enabled, GroupCategory and GroupScope are derived, not stored, so the fetch
# carries userAccountControl and groupType in their place.
@dataclass(frozen=True)
class ClassSpec:
    type_name: str
    object_class: str
    fetch: tuple[str, ...]


SPECS = {
    "user": ClassSpec(
        type_name="SambaAD.User",
        object_class="user",
        fetch=("distinguishedName", "givenName", "name", "objectClass", "objectGUID",
               "sAMAccountName", "objectSid", "sn", "userPrincipalName",
               "userAccountControl"),
    ),
    "computer": ClassSpec(
        type_name="SambaAD.Computer",
        object_class="computer",
        fetch=("distinguishedName", "dNSHostName", "name", "objectClass", "objectGUID",
               "sAMAccountName", "objectSid", "userAccountControl"),
    ),
    "group": ClassSpec(
        type_name="SambaAD.Group",
        object_class="group",
        fetch=("distinguishedName", "groupType", "name", "objectClass", "objectGUID",
               "sAMAccountName", "objectSid"),
    ),
    "object": ClassSpec(
        type_name="SambaAD.Object",
        object_class="",
        fetch=("distinguishedName", "name", "objectClass", "objectGUID"),
    ),
}
