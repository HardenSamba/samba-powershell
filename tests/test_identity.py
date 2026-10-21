"""Tests for -Identity classification and the filter it produces."""

from __future__ import annotations

import pytest

from samba_powershell.identity import classify_identity, identity_filter, is_valid_dn

FORMS = [
    ("CN=Alice,OU=Staff,DC=example,DC=com", "distinguishedName"),
    ("S-1-5-21-1004336348-1177238915-682003330-512", "objectSid"),
    ("f81d4fae-7dec-11d0-a765-00a0c91e6bf6", "objectGUID"),
    ("F81D4FAE-7DEC-11D0-A765-00A0C91E6BF6", "objectGUID"),
    ("alice", "sAMAccountName"),
    ("alice.smith", "sAMAccountName"),
]


# Each identity form is recognised from its own shape alone.
@pytest.mark.parametrize(("identity", "expected"), FORMS)
def test_identity_form_is_recognised(identity: str, expected: str) -> None:
    assert classify_identity(identity) == expected


# A sAMAccountName becomes a plain equality filter.
def test_account_name_filter() -> None:
    assert identity_filter("alice") == "(sAMAccountName=alice)"


# A distinguished name keeps its own equal signs inside the assertion.
def test_distinguished_name_filter() -> None:
    assert identity_filter("CN=Alice,DC=example,DC=com") == (
        "(distinguishedName=CN=Alice,DC=example,DC=com)"
    )


# A SID is matched in its textual form, which the directory accepts.
def test_sid_filter() -> None:
    assert identity_filter("S-1-5-32-544") == "(objectSid=S-1-5-32-544)"


# A GUID has to travel as escaped little-endian bytes, not as its text.
def test_guid_filter_is_escaped_binary() -> None:
    built = identity_filter("f81d4fae-7dec-11d0-a765-00a0c91e6bf6")
    assert built == (
        "(objectGUID=\\ae\\4f\\1d\\f8\\ec\\7d\\d0\\11"
        "\\a7\\65\\00\\a0\\c9\\1e\\6b\\f6)"
    )


# An account name carrying filter metacharacters cannot escape its assertion.
def test_account_name_metacharacters_are_escaped() -> None:
    assert identity_filter("a)(b*") == "(sAMAccountName=a\\29\\28b\\2a)"


# The distinguished names ldb accepts pass the shape check: escapes, hex pairs,
# quoted values with commas inside, multi-valued RDNs and spaces around '='.
@pytest.mark.parametrize("identity", [
    "CN=Doe\\, Jane,CN=Users,DC=example,DC=com",
    "CN=Doe\\2C Jane,CN=Users,DC=example,DC=com",
    'CN="Doe, Jane",CN=Users,DC=example,DC=com',
    "CN=Jane+UID=jdoe,DC=example,DC=com",
    "CN = Jane , DC = example",
    "2.5.4.3=Jane,DC=example,DC=com",
])
def test_well_formed_dns_are_accepted(identity: str) -> None:
    assert is_valid_dn(identity)


# Empty components, empty values and a dangling escape are refused.
@pytest.mark.parametrize("identity", ["CN=", "CN=a,,DC=b", "CN=a\\", 'CN="",DC=b', "CN=a,"])
def test_malformed_dns_are_refused(identity: str) -> None:
    assert not is_valid_dn(identity)
