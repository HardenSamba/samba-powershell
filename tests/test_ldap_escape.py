"""Tests for RFC 4515 assertion value escaping."""

from __future__ import annotations

import pytest

from samba_powershell.ldap_escape import escape_pattern, escape_value

RESERVED = [
    ("*", "\\2a"),
    ("(", "\\28"),
    (")", "\\29"),
    ("\\", "\\5c"),
    ("\x00", "\\00"),
]


# Each character reserved by RFC 4515 section 3 becomes its hex escape.
@pytest.mark.parametrize(("raw", "expected"), RESERVED)
def test_reserved_character_is_escaped(raw: str, expected: str) -> None:
    assert escape_value(raw) == expected


# An unreserved character crosses the escaper untouched.
def test_ordinary_text_is_untouched() -> None:
    assert escape_value("Année 2026") == "Année 2026"


# A backslash is escaped once, never re-escaped into its own output.
def test_backslash_is_not_doubly_escaped() -> None:
    assert escape_value("a\\*b") == "a\\5c\\2ab"


# The wildcard survives a -like pattern while the rest stays escaped.
def test_pattern_keeps_only_the_wildcard() -> None:
    assert escape_pattern("a*b)c(") == "a*b\\29c\\28"
