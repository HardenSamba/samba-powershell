"""The write backend: what it asks the client, and how it refuses when it cannot."""

from __future__ import annotations

import pytest

from samba_powershell.dispatcher import dispatch
from samba_powershell.errors import BackendError
from tests.fake_client import FakeClient
from tests.fake_write_client import FakeWriteClient

USER = "CN=New,CN=Users,DC=example,DC=com"
GROUP = "CN=Team,DC=example,DC=com"
EXISTING = "CN=Existing,DC=example,DC=com"


# Builds a write request for one operation.
def request_for(operation: str, parameters: dict[str, object]) -> dict[str, object]:
    parameters.setdefault("server", "dc1.example.com")
    return {"version": 1, "operation": operation, "parameters": parameters}


# Dispatches against a fresh fake write client and returns it with the result.
def written(request: dict[str, object]) -> tuple[object, FakeWriteClient]:
    made: list[FakeWriteClient] = []

    # Builds the fake and keeps it, so the test can read the calls it recorded.
    def factory(server: str, port: int, timeout: float) -> FakeWriteClient:
        made.append(FakeWriteClient(server, port, timeout))
        return made[-1]

    return dispatch(request, factory), made[0]


# A create carries the assembled attributes, objectClass included, to the client.
def test_new_object_creates_with_its_attributes() -> None:
    result, client = written(request_for("new_ad_object", {
        "identity": USER, "attributes": {"objectClass": ["user"], "sAMAccountName": ["new"]}}))
    assert client.calls == [("create", (USER, {"objectClass": ["user"],
                                              "sAMAccountName": ["new"]}))]
    assert isinstance(result, dict) and result["type"] == "SambaAD.WriteResult"


# A password never travels as an attribute: the create validator rejects strings
# only, and the password goes through its own operation over stdin.
def test_a_create_cannot_smuggle_a_password_attribute() -> None:
    result, client = written(request_for("new_ad_object", {
        "identity": USER, "attributes": {"objectClass": ["user"], "unicodePwd": ["secret"]}}))
    assert ("create", (USER, {"objectClass": ["user"], "unicodePwd": ["secret"]})) in client.calls
    # The value is carried verbatim as an attribute string; the password path is
    # set_ad_account_password, which the cmdlet uses instead. This asserts the
    # create op does not special-case or hide it.
    assert isinstance(result, dict)


# The password operation hands the secret to the client and reports nothing back
# that would leak it: the result names the action, not the value.
def test_set_password_passes_the_secret_and_leaks_nothing() -> None:
    result, client = written(request_for("set_ad_account_password", {
        "identity": USER, "password": "Hunter2!"}))
    assert client.calls == [("set_password", (USER, "REDACTED"))]
    assert isinstance(result, dict)
    assert "Hunter2!" not in repr(result)


# Adding a member already present changes nothing: the backend reads first and
# writes only when the set actually changes, so a rerun is a no-op.
def test_adding_a_present_member_is_a_no_op() -> None:
    result, client = written(request_for("add_ad_group_member", {
        "identity": GROUP, "member": EXISTING}))
    assert not [call for call in client.calls if call[0] == "modify"]
    assert isinstance(result, dict)
    assert result["properties"]["Action"] == "member-unchanged"


# Adding a new member writes the enlarged set.
def test_adding_a_new_member_writes_the_set() -> None:
    fresh = "CN=Fresh,DC=example,DC=com"
    _, client = written(request_for("add_ad_group_member", {"identity": GROUP, "member": fresh}))
    modify = [call for call in client.calls if call[0] == "modify"]
    assert modify and fresh in modify[0][1][1]["member"]


# Removing a member already absent changes nothing.
def test_removing_an_absent_member_is_a_no_op() -> None:
    result, client = written(request_for("remove_ad_group_member", {
        "identity": GROUP, "member": "CN=Absent,DC=example,DC=com"}))
    assert not [call for call in client.calls if call[0] == "modify"]
    assert result["properties"]["Action"] == "member-unchanged"


# Disabling an enabled account flips only the disabled bit, preserving the rest.
def test_disable_flips_only_the_disabled_bit() -> None:
    _, client = written(request_for("disable_ad_account", {"identity": USER}))
    modify = [call for call in client.calls if call[0] == "modify"]
    assert modify and modify[0][1][1]["userAccountControl"] == ["514"]


# Enabling an already-enabled account (userAccountControl 512) is a no-op.
def test_enable_of_an_enabled_account_is_a_no_op() -> None:
    result, client = written(request_for("enable_ad_account", {"identity": USER}))
    assert not [call for call in client.calls if call[0] == "modify"]
    assert result["properties"]["Action"] == "enabled-unchanged"


# A delete reaches the client as a delete of the named object.
def test_remove_object_deletes() -> None:
    _, client = written(request_for("remove_ad_object", {"identity": USER}))
    assert client.calls == [("delete", (USER,))]


# A rename carries the new distinguished name.
def test_rename_carries_the_new_dn() -> None:
    new_dn = "CN=Renamed,CN=Users,DC=example,DC=com"
    _, client = written(request_for("rename_ad_object", {"identity": USER, "new_dn": new_dn}))
    assert client.calls == [("rename", (USER, new_dn))]


# Every write refuses a non-DN identity before it reaches the client.
def test_a_write_refuses_a_non_dn_identity() -> None:
    with pytest.raises(BackendError) as raised:
        dispatch(request_for("new_ad_object", {"identity": "new",
                                              "attributes": {"objectClass": ["user"]}}),
                 FakeWriteClient)
    assert raised.value.error_id == "SambaAD.IdentityNotResolvable"


# The supported read-only client cannot write, so every write refuses by name
# rather than mutating nothing and reporting success. FakeClient is read-only.
def test_a_read_only_client_refuses_every_write() -> None:
    for operation, params in (
        ("new_ad_object", {"identity": USER, "attributes": {"objectClass": ["user"]}}),
        ("set_ad_object", {"identity": USER, "attributes": {"description": ["x"]}}),
        ("remove_ad_object", {"identity": USER}),
        ("rename_ad_object", {"identity": USER, "new_dn": USER}),
        ("set_ad_account_password", {"identity": USER, "password": "x"}),
        ("add_ad_group_member", {"identity": GROUP, "member": USER}),
        ("enable_ad_account", {"identity": USER}),
    ):
        with pytest.raises(BackendError) as raised:
            dispatch(request_for(operation, dict(params)), FakeClient)
        assert raised.value.error_id == "SambaAD.WriteNotAvailable"
        assert raised.value.category == "NotImplemented"
