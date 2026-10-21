"""Tests for turning every -Identity form into the reference a read sends."""

from __future__ import annotations

import pytest

from tests.backend_calls import answered, refused, request_for
from tests.fake_client import DOMAIN

ALICE_DN = "CN=Alice,CN=Users,DC=example,DC=com"
PC01_DN = "CN=PC01,CN=Computers,DC=example,DC=com"


# An account name is found by a sAMAccountName search of the domain, scoped to
# the cmdlet's class, and the object is then read by the name it resolved to.
def test_an_account_name_resolves_through_a_search() -> None:
    properties, client = answered(request_for("get_ad_user", "alice"))
    assert properties["DistinguishedName"] == ALICE_DN
    base, scope, ldap_filter = client.searches[0]
    assert (base, scope) == (DOMAIN, "Subtree")
    assert ldap_filter == (
        "(&(objectClass=user)(!(objectClass=computer))(sAMAccountName=alice))")
    assert client.references == [ALICE_DN]


# A SID travels as the extended reference the directory resolves on its own,
# so it costs no search.
def test_a_sid_travels_as_an_extended_reference() -> None:
    properties, client = answered(request_for("get_ad_user", "S-1-5-21-1-2-3-1105"))
    assert properties["SamAccountName"] == "alice"
    assert client.references == ["<SID=S-1-5-21-1-2-3-1105>"]
    assert client.searches == []


# A GUID travels the same way, in braces or not, as PowerShell prints it either way.
@pytest.mark.parametrize("identity", ["f81d4fae-7dec-11d0-a765-00a0c91e6bf6",
                                      "{F81D4FAE-7DEC-11D0-A765-00A0C91E6BF6}"])
def test_a_guid_travels_as_an_extended_reference(identity: str) -> None:
    properties, client = answered(request_for("get_ad_object", identity))
    assert properties["DistinguishedName"] == ALICE_DN
    assert client.references == ["<GUID=f81d4fae-7dec-11d0-a765-00a0c91e6bf6>"]


# A computer's account name may leave its trailing '$' out, as on Windows.
def test_a_computer_name_needs_no_dollar() -> None:
    properties, client = answered(request_for("get_ad_computer", "PC01"))
    assert properties["DistinguishedName"] == PC01_DN
    assert "(sAMAccountName=PC01$)" in client.searches[0][2]


# Get-ADUser leaves computers alone although computer inherits from user: by
# distinguished name the class guard refuses, by account name the search does.
def test_get_ad_user_refuses_a_computer() -> None:
    by_dn = refused(request_for("get_ad_user", PC01_DN))
    assert by_dn.error_id == "SambaAD.ObjectNotFound"
    by_name = refused(request_for("get_ad_user", "PC01$"))
    assert by_name.error_id == "SambaAD.ObjectNotFound"
    assert by_name.target == "PC01$"


# An account name two objects share is refused rather than picked from.
def test_an_ambiguous_account_name_is_refused() -> None:
    error = refused(request_for("get_ad_user", "twin"))
    assert error.error_id == "SambaAD.IdentityNotUnique"
    assert error.target == "twin"


# An account name nothing holds is not found, against the name the caller gave,
# in the one wording every not-found uses.
def test_an_unknown_account_name_is_not_found() -> None:
    error = refused(request_for("get_ad_group", "nobody"))
    assert (error.error_id, error.category, error.target) == (
        "SambaAD.ObjectNotFound", "ObjectNotFound", "nobody")
    assert error.message == "Cannot find an object with identity 'nobody'."


# An object of the wrong class reads exactly like one that does not exist.
def test_the_wrong_class_reads_like_a_missing_object() -> None:
    error = refused(request_for("get_ad_user", PC01_DN))
    assert error.message == f"Cannot find an object with identity '{PC01_DN}'."


# A control character is refused: the directory would compare only up to a NUL
# and silently resolve the prefix.
@pytest.mark.parametrize("identity", ["alice\x00xyz", "CN=Alice\x01,DC=example,DC=com",
                                      "S-1-5-21-1-2-3-1105\x00"])
def test_a_control_character_is_refused(identity: str) -> None:
    error = refused(request_for("get_ad_user", identity))
    assert (error.error_id, error.category) == ("SambaAD.InvalidIdentity", "InvalidArgument")


# A missing distinguished name is reported against the caller's identity, with
# the message Windows gives rather than the server's raw fault text.
def test_a_missing_dn_is_not_found_against_the_identity() -> None:
    missing = "CN=Nobody,CN=Users,DC=example,DC=com"
    error = refused(request_for("get_ad_user", missing))
    assert (error.error_id, error.target) == ("SambaAD.ObjectNotFound", missing)
    assert error.message == f"Cannot find an object with identity '{missing}'."


# Get-ADObject takes a distinguished name, a GUID or a SID, as on Windows; an
# account name is refused by name and costs no search.
def test_get_ad_object_refuses_an_account_name() -> None:
    error = refused(request_for("get_ad_object", "alice"))
    assert error.error_id == "SambaAD.IdentityNotResolvable"
    assert "Get-ADUser" in error.message


# A malformed distinguished name is refused before it travels.
@pytest.mark.parametrize("identity", ["CN=", "CN=a,,DC=b", "CN=a\\", "CN=a,DC="])
def test_a_malformed_dn_is_refused(identity: str) -> None:
    error = refused(request_for("get_ad_object", identity))
    assert (error.error_id, error.target) == ("SambaAD.InvalidIdentity", identity)


# Whitespace a paste carries around an identity is not part of it.
def test_surrounding_whitespace_is_ignored() -> None:
    properties, client = answered(request_for("get_ad_user", f"  {ALICE_DN} "))
    assert client.references == [ALICE_DN]
    assert properties["SamAccountName"] == "alice"
