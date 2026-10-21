"""Classification of an -Identity value and the LDAP filter it implies."""

from __future__ import annotations

import re
import uuid

from samba_powershell.ldap_escape import escape_value

GUID_HEX = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
SID_TEXT = re.compile(r"S-1-\d+(?:-\d+)+", re.IGNORECASE)
GUID_TEXT = re.compile(rf"{GUID_HEX}|\{{{GUID_HEX}\}}", re.IGNORECASE)
ATTRIBUTE_TYPE = r"(?:[A-Za-z][A-Za-z0-9-]*|[0-9]+(?:\.[0-9]+)*)"
DISTINGUISHED_NAME = re.compile(rf"{ATTRIBUTE_TYPE}\s*=")
EXTENDED_REFERENCE = re.compile(r"<(?:GUID|SID)=[^<>]+>(?:;.*)?", re.IGNORECASE)

# RFC 4514 section 3: attribute=value pairs joined by ',' or '+', where a value
# is never empty, may not start with a space, and escapes any character with a
# backslash. A trailing lone backslash or an empty component is malformed.
RDN = rf"\s*{ATTRIBUTE_TYPE}\s*=\s*(?:[^,+\\\s]|\\.)(?:[^,+\\]|\\.)*"
VALID_DN = re.compile(rf"{RDN}(?:[,+]{RDN})*")


# Names the attribute an -Identity value should be matched against. The
# account-name form is what is left: a sAMAccountName cannot hold '='.
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


# The GUID in the bare form the directory prints, braces or not on the way in.
def bare_guid(identity: str) -> str:
    return str(uuid.UUID(identity))


# Whether a distinguished name is well formed, so a typo is refused by name
# rather than answered with a not-found from a server that never parsed it.
def is_valid_dn(identity: str) -> bool:
    return VALID_DN.fullmatch(identity) is not None
