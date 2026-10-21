"""Rendering of directory attributes into the properties PowerShell shows."""

from __future__ import annotations

from collections.abc import Mapping

from samba_powershell.object_classes import ClassSpec
from samba_powershell.properties import WILDCARD
from samba_powershell.schema import AttributeInfo, is_multi
from samba_powershell.values.derive import derived_properties
from samba_powershell.values.typed import is_time, rendered_value

# The default-set attributes whose PowerShell property carries another name.
# An attribute outside the cmdlet's default set keeps its LDAP display name,
# which is what Windows does with the extra properties an administrator names.
RENAMED = {
    "distinguishedname": "DistinguishedName", "name": "Name",
    "objectguid": "ObjectGUID", "objectsid": "SID", "samaccountname": "SamAccountName",
    "sn": "Surname", "givenname": "GivenName", "userprincipalname": "UserPrincipalName",
    "dnshostname": "DNSHostName", "objectclass": "ObjectClass",
}
# Fetched so a property can be derived; shown raw only when asked for by name
# or under -Properties *.
DERIVATION_SOURCES = {"useraccountcontrol", "grouptype"}


# The names one attribute shows under: a default-set attribute takes its
# PowerShell name, and asked for by name it keeps its LDAP name beside it when
# the two differ by more than case, as Windows shows sn beside Surname.
def shown_names(key: str, label: str, defaults: set[str], asked: set[str]) -> list[str]:
    if key not in defaults:
        return [label]
    renamed = RENAMED.get(key, label)
    if key in asked and renamed.lower() != key:
        return [renamed, label]
    return [renamed]


# The cmdlet's own property names that are not attribute names, such as SID,
# Surname or GroupScope: already shown, so -Properties takes them as asking for
# nothing more, as Windows does.
def own_names(spec: ClassSpec) -> set[str]:
    renamed = {RENAMED.get(name.lower(), name).lower() for name in spec.fetch}
    return (renamed - {name.lower() for name in spec.fetch}) | {
        name.lower() for name in spec.derived}


# Every property the object promises, present even when the directory holds no
# value for it: null, or an empty list for a multi-valued attribute asked for
# by name. Windows does the same, so one result set has one shape.
def seeded(spec: ClassSpec, named: list[str],
           schema: Mapping[str, AttributeInfo]) -> dict[str, object]:
    defaults = {name.lower() for name in spec.fetch}
    asked = {name.lower() for name in named}
    out: dict[str, object] = {name: None for name in spec.derived}
    out.update({RENAMED.get(name.lower(), name): None for name in spec.fetch
                if name.lower() not in DERIVATION_SOURCES})
    for name in named:
        info = schema.get(name.lower())
        empty: object = [] if is_multi(name.lower(), info, spec.single_valued) else None
        for shown in shown_names(name.lower(), info.name if info else name, defaults, asked):
            out.setdefault(shown, empty)
    return out


# Whether one returned attribute belongs in the answer: anything asked for by
# name, the default set less its derivation sources, and under -Properties *
# every stored attribute, but none the server computes or adds of its own.
def visible(key: str, defaults: set[str], asked: set[str], everything: bool,
            info: AttributeInfo | None) -> bool:
    if key in asked:
        return True
    if key in DERIVATION_SOURCES:
        return everything
    if key in defaults:
        return True
    return everything and info is not None and not info.constructed


# Everything one object shows, ordered by name without regard to case, and the
# names holding times, which PowerShell reads back as DateTime. The wildcard asks
# for every attribute by name, so sn shows beside Surname as on Windows.
def render(attributes: Mapping[str, object], spec: ClassSpec, extras: list[str],
           schema: Mapping[str, AttributeInfo]) -> tuple[dict[str, object], list[str]]:
    named = [name for name in extras if name != WILDCARD]
    everything = WILDCARD in extras
    defaults = {name.lower() for name in spec.fetch}
    asked = {name.lower() for name in named}
    labelled = asked | defaults if everything else asked
    out = seeded(spec, named, schema)
    times: list[str] = []
    for name, value in attributes.items():
        key = name.lower()
        info = schema.get(key)
        if not visible(key, defaults, asked, everything, info):
            continue
        syntax = info.syntax if info else ""
        multi = is_multi(key, info, spec.single_valued)
        names = shown_names(key, info.name if info else name, defaults, labelled)
        out.update({shown: rendered_value(key, value, syntax, multi) for shown in names})
        if is_time(key, syntax):
            times.extend(names)
    out.update(derived_properties(attributes, spec))
    return dict(sorted(out.items(), key=lambda item: item[0].casefold())), sorted(times)
