"""Conversion of one attribute value by the syntax the schema gives it."""

from __future__ import annotations

import base64

from samba_powershell.values.derive import leaf_class, numeric
from samba_powershell.values.guid import decode_guid
from samba_powershell.values.sid import decode_sid
from samba_powershell.values.times import (
    GENERALIZED_TIME,
    decode_generalized_time,
    decode_interval_time,
)

# attributeSyntax OIDs from the syntax table of [MS-ADTS]. The endpoint carries
# every one of these as text, so the schema says a value is a number or a flag.
BOOLEAN = "2.5.5.8"
INTEGER = "2.5.5.9"
LARGE_INTEGER = "2.5.5.16"
TIME = "2.5.5.11"
SID = "2.5.5.17"
GENERALIZED_TIMES = {"whencreated", "whenchanged"}
INTERVAL_TIMES = {"pwdlastset", "accountexpires", "lastlogontimestamp", "lastlogon",
                  "badpasswordtime", "lockouttime"}
TRUTH = {"true": True, "false": False}


# One value as JSON can carry it: interval times as ISO text or nothing,
# directory times as ISO text, flags as booleans, counts as integers, binary
# decoded where its meaning is known. An empty syntax means the schema was not
# consulted, and only the attributes known by name are converted.
def converted(key: str, value: object, syntax: str) -> object:
    if isinstance(value, bytes):
        return binary(key, value, syntax)
    if not isinstance(value, str):
        return value
    if key in INTERVAL_TIMES:
        decoded = decode_interval_time(numeric(key, value))
        return decoded.isoformat() if decoded is not None else None
    if key in GENERALIZED_TIMES or syntax == TIME:
        return time_text(value)
    if syntax == BOOLEAN:
        return TRUTH.get(value.strip().lower(), value)
    if syntax in (INTEGER, LARGE_INTEGER) and value.strip().lstrip("-").isdigit():
        return int(value)
    return value


# A binary value: objectGUID and every SID-syntax attribute decoded to the
# text Windows prints, anything else base64 rather than a decode guess.
def binary(key: str, value: bytes, syntax: str) -> str:
    if key == "objectguid":
        return decode_guid(value)
    if key == "objectsid" or syntax == SID:
        return decode_sid(value)
    return base64.b64encode(value).decode("ascii")


# A directory time as ISO text. A UTC-time value, the two-digit-year form a few
# attributes still use, is left as the server sent it rather than guessed at.
def time_text(value: str) -> str:
    if GENERALIZED_TIME.fullmatch(value) is None:
        return value
    return decode_generalized_time(value).isoformat()


# One attribute as rendered: objectClass reduces to the class the object is,
# and an attribute the schema declares multi-valued is a list even when it
# holds a single value, so its shape never depends on how many values it has.
def rendered_value(key: str, value: object, syntax: str, multi: bool) -> object:
    if key == "objectclass":
        return leaf_class(value)
    if isinstance(value, tuple):
        return [converted(key, item, syntax) for item in value]
    single = converted(key, value, syntax)
    return [single] if multi else single
