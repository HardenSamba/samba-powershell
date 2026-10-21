"""What the schema says about the attributes a read asked for by name."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from samba_powershell.attributes import find
from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.ldap_escape import escape_value

SCHEMA_FIELDS = ("lDAPDisplayName", "attributeSyntax", "isSingleValued", "systemFlags")

# The systemFlags bit [MS-ADTS] names FLAG_ATTR_IS_CONSTRUCTED: the server
# computes the attribute on read instead of storing it.
CONSTRUCTED = 0x00000004


# One attribute as the renderer needs it: its display name as the schema
# spells it, its syntax OID, whether it holds one value, and whether the
# server computes it.
@dataclass(frozen=True)
class AttributeInfo:
    name: str
    syntax: str
    single_valued: bool
    constructed: bool


# Looks every named attribute up in one search of the schema naming context,
# keyed by lower-case name. A name the schema does not know is simply absent.
def describe(directory: DirectoryClient, names: Iterable[str]) -> dict[str, AttributeInfo]:
    wanted = sorted({name.lower() for name in names})
    if not wanted:
        return {}
    base = directory.naming_context("schemaNamingContext")
    clauses = "".join(f"(lDAPDisplayName={escape_value(name)})" for name in wanted)
    ldap_filter = f"(&(objectClass=attributeSchema)(|{clauses}))"
    found = directory.search(base, "OneLevel", ldap_filter, SCHEMA_FIELDS, len(wanted))
    entries = [entry for entry in map(attribute_info, found) if entry is not None]
    return {entry.name.lower(): entry for entry in entries}


# Whether an attribute renders as a list: the schema declares it multi-valued
# and the cmdlet does not keep it to one value, as security principals keep
# description. Without a schema entry the value keeps the shape it came in.
def is_multi(key: str, info: AttributeInfo | None, single: tuple[str, ...]) -> bool:
    return info is not None and not info.single_valued and key not in single


# One schema entry, or None when it lacks the fields that make it usable.
def attribute_info(entry: Mapping[str, object]) -> AttributeInfo | None:
    name = find(entry, "lDAPDisplayName")
    syntax = find(entry, "attributeSyntax")
    if not isinstance(name, str) or not isinstance(syntax, str):
        return None
    single = str(find(entry, "isSingleValued")).strip().lower() == "true"
    flags = find(entry, "systemFlags")
    computed = isinstance(flags, str) and flags.lstrip("-").isdigit() and (
        int(flags) & CONSTRUCTED != 0)
    return AttributeInfo(name, syntax, single, bool(computed))
