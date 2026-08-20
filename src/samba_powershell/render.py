"""Rendering of directory attributes into the properties PowerShell shows."""

from __future__ import annotations

import base64
from collections.abc import Mapping

from samba_powershell.object_classes import ClassSpec
from samba_powershell.values.account_control import is_enabled
from samba_powershell.values.derive import group_category, group_scope, leaf_class, numeric
from samba_powershell.values.guid import decode_guid
from samba_powershell.values.sid import decode_sid
from samba_powershell.values.times import decode_generalized_time, decode_interval_time

# The attributes whose PowerShell property carries another name. Anything not
# named here keeps its LDAP display name, which is what Windows does with the
# extra properties an administrator asks for.
RENAMED = {
    "distinguishedname": "DistinguishedName", "name": "Name",
    "objectguid": "ObjectGUID", "objectsid": "SID", "samaccountname": "SamAccountName",
    "sn": "Surname", "givenname": "GivenName", "userprincipalname": "UserPrincipalName",
    "dnshostname": "DNSHostName", "objectclass": "ObjectClass",
}
GENERALIZED_TIMES = {"whencreated", "whenchanged"}
INTERVAL_TIMES = {"pwdlastset", "accountexpires", "lastlogontimestamp", "lastlogon",
                  "badpasswordtime", "lockouttime"}
# Fetched so a property can be derived; shown raw only when asked for by name.
DERIVATION_SOURCES = {"useraccountcontrol", "grouptype"}


# One attribute value as JSON can carry it: binary decoded where its meaning is
# known, base64 where it is not, and the two time encodings as ISO text.
def _scalar(key: str, value: object) -> object:
    if key == "objectguid" and isinstance(value, bytes):
        return decode_guid(value)
    if key == "objectsid" and isinstance(value, bytes):
        return decode_sid(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if key in GENERALIZED_TIMES and isinstance(value, str):
        return decode_generalized_time(value).isoformat()
    if key in INTERVAL_TIMES and isinstance(value, str):
        decoded = decode_interval_time(numeric(key, value))
        return decoded.isoformat() if decoded is not None else None
    return value


# One attribute as rendered: objectClass reduces to the class the object is,
# a multi-valued attribute becomes a list, a single value stays scalar.
def rendered_value(key: str, value: object) -> object:
    if key == "objectclass":
        return leaf_class(value)
    if isinstance(value, tuple):
        return [_scalar(key, item) for item in value]
    return _scalar(key, value)


# The value of one attribute, found without regard to the server's casing.
def find(attributes: Mapping[str, object], name: str) -> object:
    for key, value in attributes.items():
        if key.lower() == name.lower():
            return value
    return None


# The properties Windows presents that the directory does not store, derived
# from the attributes fetched in their place.
def derived(attributes: Mapping[str, object], spec: ClassSpec) -> dict[str, object]:
    out: dict[str, object] = {}
    control = find(attributes, "userAccountControl")
    if control is not None and spec.type_name in ("SambaAD.User", "SambaAD.Computer"):
        out["Enabled"] = is_enabled(numeric("userAccountControl", control))
    group_type = find(attributes, "groupType")
    if group_type is not None and spec.type_name == "SambaAD.Group":
        out["GroupCategory"] = group_category(numeric("groupType", group_type))
        out["GroupScope"] = group_scope(numeric("groupType", group_type))
    return out


# Everything one object shows: renamed defaults, derived properties, and the
# extra attributes under their own names. A derivation source appears raw only
# when the caller asked for it by name.
def render(attributes: Mapping[str, object], spec: ClassSpec,
           extras: list[str]) -> dict[str, object]:
    asked = {name.lower() for name in extras}
    out: dict[str, object] = {}
    for name, value in attributes.items():
        key = name.lower()
        if key in DERIVATION_SOURCES and key not in asked:
            continue
        out[RENAMED.get(key, name)] = rendered_value(key, value)
    out.update(derived(attributes, spec))
    return dict(sorted(out.items()))
