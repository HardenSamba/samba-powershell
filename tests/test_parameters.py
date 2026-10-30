"""Tests for the request parameters every read shares."""

from __future__ import annotations

import pytest

from samba_powershell.dispatcher import dispatch
from samba_powershell.errors import BackendError
from samba_powershell.parameters import LDAP_PORT, requested_endpoint
from tests.backend_calls import answered, request_for
from tests.fake_client import FakeClient


# A bare host reaches LDAP's own port, the one every controller serves.
def test_the_default_port_is_ldap() -> None:
    assert requested_endpoint({"server": "dc1"}) == ("dc1", 389, "dc1")


# A server given only as whitespace is no server, and says so the same way an
# absent one does.
@pytest.mark.parametrize("server", ["", "   "])
def test_a_blank_server_is_required(server: str) -> None:
    with pytest.raises(BackendError) as raised:
        requested_endpoint({"server": server})
    assert (raised.value.error_id, raised.value.target) == ("SambaAD.ServerRequired", "Server")


# host:port names another port, as the Windows module accepts; a bare host
# takes the LDAP port, surrounding whitespace is dropped, and the value as given
# comes back beside the host and port, for a failure to report.
@pytest.mark.parametrize(("server", "endpoint"), [
    ("dc1.example.com", ("dc1.example.com", LDAP_PORT, "dc1.example.com")),
    (" dc1.example.com ", ("dc1.example.com", LDAP_PORT, "dc1.example.com")),
    ("dc1.example.com:1389", ("dc1.example.com", 1389, "dc1.example.com:1389")),
    ("dc1.example.com:636", ("dc1.example.com", 636, "dc1.example.com:636")),
])
def test_the_endpoint_is_read_from_server(server: str,
                                          endpoint: tuple[str, int, str]) -> None:
    assert requested_endpoint({"server": server}) == endpoint


# What cannot be a host name is refused against itself, before it reaches an LDAP
# URI it would corrupt: a space there starts a second server.
@pytest.mark.parametrize("server", [
    "dc1\x00.example.com", "dc1.example.com\x1b", "dc\n1", "a b", "dc1 ldap://evil", "dc1/x",
    "dc%41", 'dc"1', "dc1.example.com:notaport", "dc1.example.com:70000", ":389",
    ".example.com", "a..b", "a" * 64 + ".example.com",
])
def test_what_is_not_a_host_name_is_refused(server: str) -> None:
    with pytest.raises(BackendError) as raised:
        requested_endpoint({"server": server})
    assert (raised.value.error_id, raised.value.target) == ("SambaAD.InvalidParameter", server)


# A transport failure names the endpoint as the caller gave it, port included,
# so a wrong port is not mistaken for a stopped service.
def test_a_transport_failure_names_the_port() -> None:

    # Fails the way the session does when nothing listens on the port.
    def refusing(server: str, port: int, timeout: float) -> FakeClient:
        raise ConnectionRefusedError(111, "Connection refused")

    request = request_for("get_ad_user", "CN=Alice,CN=Users,DC=example,DC=com")
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["server"] = "dc2.example.com:1389"
    with pytest.raises(BackendError) as raised:
        dispatch(request, refusing)
    assert raised.value.target == "dc2.example.com:1389"
    assert "'dc2.example.com:1389'" in raised.value.message


# The endpoint reaches the client the backend opens.
def test_the_client_is_opened_on_the_requested_endpoint() -> None:
    request = request_for("get_ad_user", "CN=Alice,CN=Users,DC=example,DC=com")
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["server"] = "dc2.example.com:1389"
    _, client = answered(request)
    assert (client.server, client.port) == ("dc2.example.com", 1389)
