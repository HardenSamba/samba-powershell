"""Tests for directory dispatch without a reachable domain."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from samba_powershell.dispatcher import dispatch
from samba_powershell.operations import DEFAULT_USER_PROPERTIES
from samba_powershell.errors import BackendError
from tests.fake_client import FakeClient


# Builds a valid proof request for the fake client.
def proof_request() -> dict[str, object]:
    return {
        "version": 1,
        "operation": "get_ad_user",
        "parameters": {
            "identity": "CN=Alice,DC=example,DC=com",
            "server": "dc1.example.com",
            "properties": ["mail"],
        },
    }


# The requested properties the fake client saw on one dispatch.
def fetched(request: dict[str, object]) -> list[str]:
    result = dispatch(request, FakeClient)
    assert isinstance(result, dict)
    properties = result["properties"]
    assert isinstance(properties, dict)
    requested = properties["RequestedProperties"]
    assert isinstance(requested, list)
    return requested


# The read proof returns a PowerShell type name and directory properties, and
# -Properties adds to the default set rather than replacing it: an administrator
# asking for mail gets the default columns and mail, as docs/cmdlets.md decides.
def test_get_ad_user_uses_client_boundary() -> None:
    result = dispatch(proof_request(), FakeClient)
    assert isinstance(result, dict)
    assert result["type"] == "SambaAD.User"
    properties = result["properties"]
    assert isinstance(properties, dict)
    requested = properties["RequestedProperties"]
    assert isinstance(requested, list)
    assert set(DEFAULT_USER_PROPERTIES) <= set(requested)
    assert requested[-1] == "mail"


# With no -Properties, the fetch is the decided ten-property default set, with
# userAccountControl standing in for the derived Enabled.
def test_get_ad_user_fetches_the_decided_defaults() -> None:
    request = proof_request()
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["properties"] = []
    assert fetched(request) == list(DEFAULT_USER_PROPERTIES)
    assert "userAccountControl" in DEFAULT_USER_PROPERTIES
    assert len(DEFAULT_USER_PROPERTIES) == 10


# Asking for a property already in the default set, in whatever case, must not
# fetch it twice: LDAP attribute names are not case-sensitive.
def test_a_default_asked_for_again_is_not_doubled() -> None:
    request = proof_request()
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["properties"] = ["SAMAccountName", "mail"]
    requested = fetched(request)
    assert requested.count("sAMAccountName") == 1
    assert "SAMAccountName" not in requested
    assert requested[-1] == "mail"


# Missing endpoints fail before the optional samba-adws import is needed.
def test_get_ad_user_requires_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAMBA_AD_SERVER", raising=False)
    request = proof_request()
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters.pop("server")
    with pytest.raises(BackendError) as raised:
        dispatch(request, FakeClient)
    assert raised.value.error_id == "SambaAD.ServerRequired"


# Unknown operations are rejected with a stable identifier.
def test_unknown_operation_is_rejected() -> None:
    request = proof_request()
    request["operation"] = "delete_everything"
    with pytest.raises(BackendError) as raised:
        dispatch(request, FakeClient)
    assert raised.value.error_id == "SambaAD.UnsupportedOperation"


# Password fields are rejected instead of being silently copied or ignored.
def test_password_parameter_is_rejected() -> None:
    request = proof_request()
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["password"] = "do-not-accept-this"
    with pytest.raises(BackendError) as raised:
        dispatch(request, FakeClient)
    assert raised.value.error_id == "SambaAD.InvalidParameter"
    assert raised.value.target == "password"


# Client faults retain their public fields across the backend boundary.
def test_client_error_is_translated() -> None:
    failure = RuntimeError("missing")
    setattr(failure, "code", "IdentityNotFound")
    setattr(failure, "category", "ObjectNotFound")
    setattr(failure, "target", "alice")
    client = Mock()
    client.get_by_dn.side_effect = failure
    with pytest.raises(BackendError) as raised:
        dispatch(proof_request(), lambda _server, _port, _timeout: client)
    assert raised.value.error_id == "SambaAD.IdentityNotFound"
    assert raised.value.category == "ObjectNotFound"
