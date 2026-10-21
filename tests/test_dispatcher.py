"""Tests for directory dispatch without a reachable domain."""

from __future__ import annotations

import json

import pytest

from samba_powershell.dispatcher import dispatch
from samba_powershell.errors import BackendError
from samba_powershell.operations import DEFAULT_USER_PROPERTIES
from tests.backend_calls import answered, request_for
from tests.fake_client import FakeClient

ALICE_DN = "CN=Alice,CN=Users,DC=example,DC=com"
SALES_DN = "CN=Sales,DC=example,DC=com"


# The default read renders the decided property set under its PowerShell names:
# binary values decoded, Enabled derived, and the raw userAccountControl absent
# because nobody asked for it.
def test_get_ad_user_renders_the_decided_defaults() -> None:
    properties, client = answered(request_for("get_ad_user", ALICE_DN))
    assert client.requested == list(DEFAULT_USER_PROPERTIES)
    assert properties["DistinguishedName"] == ALICE_DN
    assert properties["SamAccountName"] == "alice"
    assert properties["Surname"] == "Liddell"
    assert properties["ObjectClass"] == "user"
    assert properties["ObjectGUID"] == "f81d4fae-7dec-11d0-a765-00a0c91e6bf6"
    assert properties["SID"] == "S-1-5-21-1-2-3-1105"
    assert properties["Enabled"] is True
    assert "userAccountControl" not in properties


# A read of the default set costs one exchange: no schema lookup, no search.
def test_a_default_read_asks_nothing_else() -> None:
    _, client = answered(request_for("get_ad_user", ALICE_DN))
    assert client.searches == []
    assert client.references == [ALICE_DN]


# -Properties adds to the default set rather than replacing it, and the extra
# attribute appears under its own LDAP name, the way Windows shows it.
def test_properties_add_to_the_defaults() -> None:
    properties, client = answered(request_for("get_ad_user", ALICE_DN, ["mail"]))
    assert set(DEFAULT_USER_PROPERTIES) <= set(client.requested)
    assert client.requested[-1] == "mail"
    assert properties["mail"] == "alice@example.com"
    assert properties["SamAccountName"] == "alice"


# Asking for a default again, in another case, must not fetch it twice.
def test_a_default_asked_for_again_is_not_doubled() -> None:
    _, client = answered(request_for("get_ad_user", ALICE_DN, ["SAMAccountName", "mail"]))
    assert client.requested.count("sAMAccountName") == 1
    assert "SAMAccountName" not in client.requested


# Time-encoded attributes render as ISO text, the never sentinel as nothing,
# and a multi-valued attribute as a list. The whole answer survives JSON,
# because JSON is the channel it crosses to PowerShell.
def test_times_lists_and_json_safety() -> None:
    extras = ["whenCreated", "pwdLastSet", "accountExpires", "memberOf"]
    properties, _ = answered(request_for("get_ad_user", ALICE_DN, extras))
    assert properties["whenCreated"] == "2024-02-29T12:00:00+00:00"
    when_set = properties["pwdLastSet"]
    assert isinstance(when_set, str) and when_set.startswith("2024-")
    assert properties["accountExpires"] is None
    assert properties["memberOf"] == [SALES_DN, "CN=Staff,DC=example,DC=com"]
    assert json.dumps(properties)


# A derivation source asked for by name appears raw beside the derived value,
# as the integer its Integer syntax says it is.
def test_a_derivation_source_appears_when_asked_for() -> None:
    properties, _ = answered(request_for("get_ad_user", ALICE_DN, ["userAccountControl"]))
    assert properties["userAccountControl"] == 512
    assert properties["Enabled"] is True


# A group renders its category and scope from groupType, which stays hidden
# unless asked for, exactly like userAccountControl.
def test_get_ad_group_derives_category_and_scope() -> None:
    properties, _ = answered(request_for("get_ad_group", SALES_DN))
    assert properties["GroupCategory"] == "Security"
    assert properties["GroupScope"] == "Global"
    assert "groupType" not in properties


# The wrong cmdlet does not find the object, the way Windows reports it.
def test_the_class_guard_refuses_the_wrong_kind() -> None:
    with pytest.raises(BackendError) as raised:
        dispatch(request_for("get_ad_user", SALES_DN), FakeClient)
    assert raised.value.error_id == "SambaAD.ObjectNotFound"
    with pytest.raises(BackendError) as raised:
        dispatch(request_for("get_ad_group", ALICE_DN), FakeClient)
    assert raised.value.category == "ObjectNotFound"


# Get-ADObject takes any class and asks for no more than its four defaults.
def test_get_ad_object_takes_any_class() -> None:
    properties, client = answered(request_for("get_ad_object", SALES_DN))
    assert properties["ObjectClass"] == "group"
    assert client.requested == ["distinguishedName", "name", "objectClass", "objectGUID"]


# Missing endpoints fail before the optional samba-adws import is needed.
def test_get_ad_user_requires_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAMBA_AD_SERVER", raising=False)
    request = request_for("get_ad_user", ALICE_DN)
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters.pop("server")
    with pytest.raises(BackendError) as raised:
        dispatch(request, FakeClient)
    assert raised.value.error_id == "SambaAD.ServerRequired"


# Unknown operations are rejected with a stable identifier.
def test_unknown_operation_is_rejected() -> None:
    request = request_for("get_ad_user", ALICE_DN)
    request["operation"] = "delete_everything"
    with pytest.raises(BackendError) as raised:
        dispatch(request, FakeClient)
    assert raised.value.error_id == "SambaAD.UnsupportedOperation"


# Password fields are rejected instead of being silently copied or ignored.
def test_password_parameter_is_rejected() -> None:
    request = request_for("get_ad_user", ALICE_DN)
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["password"] = "hunter2"
    with pytest.raises(BackendError) as raised:
        dispatch(request, FakeClient)
    assert raised.value.error_id == "SambaAD.InvalidParameter"
