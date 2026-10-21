"""Tests for the shape and the types of the objects the cmdlets return."""

from __future__ import annotations

import json

import pytest

from samba_powershell.dispatcher import dispatch
from tests.backend_calls import answered, refused, request_for
from tests.fake_client import FakeClient

ALICE_DN = "CN=Alice,CN=Users,DC=example,DC=com"
BOB_DN = "CN=Bob,CN=Users,DC=example,DC=com"
SALES_DN = "CN=Sales,DC=example,DC=com"
PC01_DN = "CN=PC01,CN=Computers,DC=example,DC=com"
USER_DEFAULTS = ["DistinguishedName", "Enabled", "GivenName", "Name", "ObjectClass",
                 "ObjectGUID", "SamAccountName", "SID", "Surname", "UserPrincipalName"]


# Every default property is present, null when the directory holds no value,
# so one result set has one shape and strict-mode scripts can read them all.
def test_unset_defaults_are_present_as_null() -> None:
    properties, _ = answered(request_for("get_ad_user", BOB_DN))
    assert list(properties) == USER_DEFAULTS
    assert properties["GivenName"] is None
    assert properties["Surname"] is None
    assert properties["UserPrincipalName"] is None
    assert properties["Enabled"] is False


# A computer without a dNSHostName still has the DNSHostName property.
def test_a_computer_without_a_host_name_keeps_the_property() -> None:
    properties, _ = answered(request_for("get_ad_computer", PC01_DN))
    assert "DNSHostName" in properties and properties["DNSHostName"] is None
    assert properties["ObjectClass"] == "computer"


# Properties are listed by name without regard to case, as Windows lists them:
# SamAccountName before SID, and lower-case LDAP names among the rest.
def test_properties_are_ordered_without_regard_to_case() -> None:
    properties, _ = answered(request_for("get_ad_user", ALICE_DN, ["mail", "logonCount"]))
    names = list(properties)
    assert names == sorted(names, key=str.casefold)
    assert names.index("SamAccountName") < names.index("SID")


# An attribute the schema declares multi-valued is a list even with one value,
# and an empty list when the object holds none; a single-valued one is null.
def test_multi_valued_attributes_are_always_lists() -> None:
    properties, _ = answered(request_for("get_ad_user", BOB_DN, ["memberOf", "mail"]))
    assert properties["memberOf"] == [SALES_DN]
    assert properties["mail"] is None
    group, _ = answered(request_for("get_ad_group", SALES_DN, ["member", "description"]))
    assert group["member"] == [ALICE_DN]
    assert group["description"] is None


# Integer, Boolean and SID syntaxes arrive typed, so comparisons and tests on
# them mean what they say; a security principal's description stays text.
def test_values_are_typed_by_their_syntax() -> None:
    extras = ["logonCount", "isCriticalSystemObject", "tokenGroups", "description"]
    properties, _ = answered(request_for("get_ad_user", ALICE_DN, extras))
    assert properties["logonCount"] == 7
    assert properties["isCriticalSystemObject"] is False
    assert properties["tokenGroups"] == ["S-1-5-21-1-2-3-513", "S-1-5-21-1-2-3-1301"]
    assert properties["description"] == "Reads the ledgers"


# A default asked for by name keeps its LDAP name beside its PowerShell name,
# and an attribute outside the cmdlet's default set is never renamed.
def test_renamed_defaults_keep_their_ldap_name_when_asked_for() -> None:
    user, _ = answered(request_for("get_ad_user", ALICE_DN, ["sn", "objectSid"]))
    assert user["Surname"] == user["sn"] == "Liddell"
    assert user["SID"] == user["objectSid"] == "S-1-5-21-1-2-3-1105"
    other, _ = answered(request_for("get_ad_object", ALICE_DN, ["objectSid", "sn"]))
    assert other["objectSid"] == "S-1-5-21-1-2-3-1105" and "SID" not in other
    assert other["sn"] == "Liddell" and "Surname" not in other


# -Properties * reads the whole object and shows every stored attribute, the
# derivation sources included, but none the server computes.
def test_the_wildcard_shows_every_stored_attribute() -> None:
    properties, client = answered(request_for("get_ad_user", ALICE_DN, ["*"]))
    assert client.requested == []
    assert properties["mail"] == "alice@example.com"
    assert properties["userAccountControl"] == 512
    assert "tokenGroups" not in properties
    assert json.dumps(properties)


# A computed attribute named beside the wildcard is shown all the same.
def test_a_named_constructed_attribute_survives_the_wildcard() -> None:
    properties, _ = answered(request_for("get_ad_user", ALICE_DN, ["*", "tokenGroups"]))
    assert properties["tokenGroups"] == ["S-1-5-21-1-2-3-513", "S-1-5-21-1-2-3-1301"]


# An attribute the server computes only when named is read again beside the
# wildcard, rather than shown as null, and stays out of a plain wildcard read.
def test_an_on_request_attribute_is_read_beside_the_wildcard() -> None:
    plain, _ = answered(request_for("get_ad_user", ALICE_DN, ["*"]))
    assert "msDS-KeyVersionNumber" not in plain
    named, client = answered(request_for("get_ad_user", ALICE_DN,
                                         ["*", "msDS-KeyVersionNumber"]))
    assert named["msDS-KeyVersionNumber"] == 2
    assert client.requested == ["msDS-KeyVersionNumber"]


# Under the wildcard a renamed default shows under both names, as on Windows.
def test_the_wildcard_keeps_ldap_names_beside_powershell_names() -> None:
    properties, _ = answered(request_for("get_ad_user", ALICE_DN, ["*"]))
    assert properties["sn"] == properties["Surname"] == "Liddell"
    assert properties["objectSid"] == properties["SID"]


# The cmdlet's own property names are already shown, so asking for them adds
# nothing and is not refused, as Windows accepts -Properties SID.
def test_the_cmdlets_own_names_are_accepted() -> None:
    user, client = answered(request_for("get_ad_user", ALICE_DN, ["SID", "Surname", "Enabled"]))
    assert client.searches == []
    assert user["SID"] == "S-1-5-21-1-2-3-1105" and user["Enabled"] is True
    group, _ = answered(request_for("get_ad_group", SALES_DN, ["GroupScope"]))
    assert group["GroupScope"] == "Global"


# The backend names the properties holding times, so PowerShell converts those
# and leaves text that merely looks like a date as text.
def test_time_properties_are_listed_and_text_is_not() -> None:
    request = request_for("get_ad_user", ALICE_DN, ["whenCreated", "pwdLastSet", "info"])
    result = dispatch(request, FakeClient)
    assert isinstance(result, dict)
    assert result["datetimes"] == ["pwdLastSet", "whenCreated"]
    properties = result["properties"]
    assert isinstance(properties, dict)
    assert properties["info"] == "2026-01-01T10:00:00+00:00"


# A property the schema does not define is refused, the way Windows refuses
# it, rather than returning an object that silently lacks it.
def test_an_unknown_property_is_refused() -> None:
    error = refused(request_for("get_ad_user", ALICE_DN, ["mail", "doesNotExist"]))
    assert (error.error_id, error.target) == ("SambaAD.InvalidProperty", "doesNotExist")
    assert error.message == ("One or more properties are invalid: 'doesNotExist' is not an "
                             "attribute the schema defines.")


# Several unknown properties are all named, in a sentence that reads right.
def test_several_unknown_properties_are_all_named() -> None:
    error = refused(request_for("get_ad_user", ALICE_DN, ["foo", "mail", "bar"]))
    assert error.message == ("One or more properties are invalid: 'foo', 'bar' are not "
                             "attributes the schema defines.")
    assert error.target == "foo"


# A name no attribute can have is refused before anything travels, with the
# reason: an attribute option, or several names in one string.
@pytest.mark.parametrize(("name", "reason"), [("member;range=0-1", "option"),
                                              ("description,systemFlags", "one LDAP"),
                                              ("", "is empty"), ("  ", "is empty")])
def test_a_malformed_property_name_is_refused(name: str, reason: str) -> None:
    error = refused(request_for("get_ad_user", ALICE_DN, [name]))
    assert error.error_id == "SambaAD.InvalidProperty"
    assert reason in error.message
