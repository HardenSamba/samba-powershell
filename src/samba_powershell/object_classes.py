"""The object classes the read cmdlets know, and what each returns by default."""

from __future__ import annotations

from dataclasses import dataclass


# One cmdlet's shape: its PowerShell type, the objectClass it accepts and the
# classes derived from it that it still refuses, the attribute fetch behind the
# default property set docs/cmdlets.md decides, and the properties derived
# rather than stored. Enabled, GroupCategory and GroupScope are not attributes,
# so the fetch carries userAccountControl and groupType in their place.
@dataclass(frozen=True)
class ClassSpec:
    type_name: str
    object_class: str
    fetch: tuple[str, ...]
    excluded: tuple[str, ...] = ()
    derived: tuple[str, ...] = ()
    account_suffix: str = ""
    account_names: bool = True
    single_valued: tuple[str, ...] = ()


# description is multi-valued in the schema, but the directory keeps one value
# on the security principals it manages, and Windows shows it as text there.
PRINCIPAL_SINGLE = ("description",)

SPECS = {
    "user": ClassSpec(
        type_name="SambaAD.User",
        object_class="user",
        fetch=("distinguishedName", "givenName", "name", "objectClass", "objectGUID",
               "sAMAccountName", "objectSid", "sn", "userPrincipalName",
               "userAccountControl"),
        excluded=("computer",),
        derived=("Enabled",),
        single_valued=PRINCIPAL_SINGLE,
    ),
    "computer": ClassSpec(
        type_name="SambaAD.Computer",
        object_class="computer",
        fetch=("distinguishedName", "dNSHostName", "name", "objectClass", "objectGUID",
               "sAMAccountName", "objectSid", "userAccountControl"),
        derived=("Enabled",),
        account_suffix="$",
        single_valued=PRINCIPAL_SINGLE,
    ),
    "group": ClassSpec(
        type_name="SambaAD.Group",
        object_class="group",
        fetch=("distinguishedName", "groupType", "name", "objectClass", "objectGUID",
               "sAMAccountName", "objectSid"),
        derived=("GroupCategory", "GroupScope"),
        single_valued=PRINCIPAL_SINGLE,
    ),
    "object": ClassSpec(
        type_name="SambaAD.Object",
        object_class="",
        fetch=("distinguishedName", "name", "objectClass", "objectGUID"),
        account_names=False,
    ),
}
