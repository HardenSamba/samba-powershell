"""Classification of an -Identity value and the LDAP filter it implies."""

from __future__ import annotations

import re
import uuid

from samba_powershell.ldap_escape import escape_value

SID_TEXT = re.compile(r"S-1-\d+(?:-\d+)+", re.IGNORECASE)
GUID_TEXT = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.IGNORECASE)
DISTINGUISHED_NAME = re.compile(r"[A-Za-z][A-Za-z0-9-]*=.+")


# Names the attribute an -Identity value should be matched against.
def classify_identity(identity: str) -> str:
    if SID_TEXT.fullmatch(identity):
        return "objectSid"
    if GUID_TEXT.fullmatch(identity):
        return "objectGUID"
    if DISTINGUISHED_NAME.match(identity):
        return "distinguishedName"
    return "sAMAccountName"


# Builds the filter matching one identity in whichever form it was given.
def identity_filter(identity: str) -> str:
    attribute = classify_identity(identity)
    if attribute == "objectGUID":
        return f"(objectGUID={guid_filter_value(identity)})"
    return f"({attribute}={escape_value(identity)})"


# Renders a GUID as the escaped little-endian bytes a filter has to carry.
def guid_filter_value(identity: str) -> str:
    raw = uuid.UUID(identity).bytes_le
    return "".join(f"\\{byte:02x}" for byte in raw)
