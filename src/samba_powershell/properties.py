"""The -Properties a read was given: checked, merged and looked up."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from samba_powershell.errors import BackendError
from samba_powershell.schema import AttributeInfo

WILDCARD = "*"
DISPLAY_NAME = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


# Reads the property names the caller asked for beyond the default set, each
# checked, and each kept once whatever its case: LDAP names have none.
def requested_extras(parameters: dict[str, object]) -> list[str]:
    value = parameters.get("properties", [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BackendError(
            "Parameter 'properties' must be an array of strings.",
            "SambaAD.InvalidParameter",
            "InvalidArgument",
            "properties",
        )
    unique: dict[str, str] = {}
    for item in value:
        name = checked_name(item.strip())
        unique.setdefault(name.lower(), name)
    return list(unique.values())


# Refuses a name no attribute can have, saying what is wrong with it. An
# attribute option such as ;range= is refused outright: it changes what a read
# returns, and the endpoint does not carry it.
def checked_name(name: str) -> str:
    if name == WILDCARD or DISPLAY_NAME.fullmatch(name):
        return name
    reason = ("carries an attribute option; options such as ;range= are not supported"
              if ";" in name else
              "is not an attribute name; give one LDAP display name per entry, as in "
              "-Properties mail,memberOf")
    raise BackendError(f"Property '{name}' {reason}.", "SambaAD.InvalidProperty",
                       "InvalidArgument", name)


# The attribute fetch for one call: the class's default set plus the names
# asked for, or the whole object when the caller asked for everything.
# -Properties adds to the defaults rather than replacing them, and a default
# asked for again in another spelling is not fetched twice.
def fetch_list(defaults: Sequence[str], extras: Sequence[str]) -> tuple[str, ...]:
    if WILDCARD in extras:
        return ()
    merged = {name.lower(): name for name in defaults}
    for name in extras:
        merged.setdefault(name.lower(), name)
    return tuple(merged.values())


# The attributes whose schema entry the renderer needs: every name asked for,
# and under -Properties * everything the object returned.
def typed_names(attributes: Mapping[str, object], extras: Sequence[str]) -> set[str]:
    names = {name.lower() for name in extras if name != WILDCARD}
    if WILDCARD in extras:
        names.update(key.lower() for key in attributes)
    return names


# Refuses a property the schema does not define, the way Windows refuses it,
# rather than returning an object that silently lacks it.
def check_known(extras: Sequence[str], schema: Mapping[str, AttributeInfo]) -> None:
    unknown = [name for name in extras if name != WILDCARD and name.lower() not in schema]
    if unknown:
        raise BackendError(
            f"One or more properties are invalid: {', '.join(unknown)} is not an attribute "
            "the schema defines.",
            "SambaAD.InvalidProperty",
            "InvalidArgument",
            unknown[0],
        )
