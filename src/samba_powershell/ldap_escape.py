"""Escaping of values interpolated into an LDAP search filter."""

from __future__ import annotations

ESCAPES = {
    "\\": "\\5c",
    "*": "\\2a",
    "(": "\\28",
    ")": "\\29",
    "\x00": "\\00",
}
PATTERN_ESCAPES = {key: value for key, value in ESCAPES.items() if key != "*"}


# Escapes every character RFC 4515 section 3 reserves in an assertion value.
def escape_value(value: str) -> str:
    return "".join(ESCAPES.get(character, character) for character in value)


# Escapes an assertion value while keeping '*' as the -like wildcard.
def escape_pattern(value: str) -> str:
    return "".join(PATTERN_ESCAPES.get(character, character) for character in value)
