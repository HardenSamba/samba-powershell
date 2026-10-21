"""Properties Windows presents that the directory does not store."""

from __future__ import annotations

from collections.abc import Mapping

from samba_powershell.attributes import find
from samba_powershell.errors import BackendError
from samba_powershell.object_classes import ClassSpec
from samba_powershell.values.account_control import is_enabled

# groupType is a bit field, [MS-ADTS] 2.2.12: one scope bit, and a sign bit
# that makes the group a security group rather than a distribution list.
GLOBAL = 0x00000002
DOMAIN_LOCAL = 0x00000004
UNIVERSAL = 0x00000008
SECURITY_ENABLED = 0x80000000


# Reads a numeric attribute value the directory rendered as text.
def numeric(name: str, value: object) -> int:
    text = value if isinstance(value, str) else ""
    if text.lstrip("-").isdigit():
        return int(text)
    raise BackendError(
        f"Attribute '{name}' should be a number, not {value!r}.",
        "SambaAD.InvalidValue",
        "InvalidData",
        name,
    )


# Whether a group carries security identifiers or only addresses mail.
def group_category(group_type: int) -> str:
    return "Security" if group_type & SECURITY_ENABLED else "Distribution"


# The replication scope of a group, from the one scope bit that is set.
def group_scope(group_type: int) -> str:
    if group_type & GLOBAL:
        return "Global"
    if group_type & UNIVERSAL:
        return "Universal"
    if group_type & DOMAIN_LOCAL:
        return "DomainLocal"
    raise BackendError(
        f"groupType {group_type:#x} carries no scope bit.",
        "SambaAD.InvalidValue",
        "InvalidData",
        "groupType",
    )


# The most specific class of an object: objectClass lists the hierarchy from
# top downwards, so the last value is the one the object actually is.
def leaf_class(value: object) -> str:
    if isinstance(value, tuple) and value:
        last = value[-1]
        return last if isinstance(last, str) else ""
    return value if isinstance(value, str) else ""


# The properties Windows presents that the directory does not store, derived
# from the attributes the cmdlet fetched in their place.
def derived_properties(attributes: Mapping[str, object], spec: ClassSpec) -> dict[str, object]:
    out: dict[str, object] = {}
    control = find(attributes, "userAccountControl")
    if control is not None and "Enabled" in spec.derived:
        out["Enabled"] = is_enabled(numeric("userAccountControl", control))
    group_type = find(attributes, "groupType")
    if group_type is not None and "GroupScope" in spec.derived:
        out["GroupCategory"] = group_category(numeric("groupType", group_type))
        out["GroupScope"] = group_scope(numeric("groupType", group_type))
    return out
