"""Tests for the request parameters every read shares."""

from __future__ import annotations

import pytest

from samba_powershell.dispatcher import dispatch
from samba_powershell.errors import BackendError
from samba_powershell.parameters import ADWS_PORT, requested_endpoint
from tests.backend_calls import answered, request_for
from tests.fake_client import FakeClient
from tests.test_client_error import ClientFailure


# A server given only as whitespace is no server, and says so the same way an
# absent one does.
@pytest.mark.parametrize("server", ["", "   "])
def test_a_blank_server_is_required(server: str) -> None:
    with pytest.raises(BackendError) as raised:
        requested_endpoint({"server": server})
    assert (raised.value.error_id, raised.value.target) == ("SambaAD.ServerRequired", "Server")


# host:port names another port, as the Windows module accepts; a bare host
# takes the ADWS port, and surrounding whitespace is dropped.
@pytest.mark.parametrize(("server", "endpoint"), [
    ("dc1.example.com", ("dc1.example.com", ADWS_PORT)),
    (" dc1.example.com ", ("dc1.example.com", ADWS_PORT)),
    ("dc1.example.com:19389", ("dc1.example.com", 19389)),
    ("dc1.example.com:notaport", ("dc1.example.com:notaport", ADWS_PORT)),
])
def test_the_endpoint_is_read_from_server(server: str, endpoint: tuple[str, int]) -> None:
    assert requested_endpoint({"server": server}) == endpoint


# A transport failure names the endpoint as the caller gave it, port included,
# so a wrong port is not mistaken for a stopped service.
def test_a_transport_failure_names_the_port() -> None:

    # Fails the way samba-adws does when nothing listens on the port.
    def refusing(server: str, port: int, timeout: float) -> FakeClient:
        raise ClientFailure("[Errno 111] Connection refused", "TransportError",
                            "ResourceUnavailable", "x")

    request = request_for("get_ad_user", "CN=Alice,CN=Users,DC=example,DC=com")
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["server"] = "dc2.example.com:19389"
    with pytest.raises(BackendError) as raised:
        dispatch(request, refusing)
    assert raised.value.target == "dc2.example.com:19389"
    assert "'dc2.example.com:19389'" in raised.value.message


# The endpoint reaches the client the backend opens.
def test_the_client_is_opened_on_the_requested_endpoint() -> None:
    request = request_for("get_ad_user", "CN=Alice,CN=Users,DC=example,DC=com")
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["server"] = "dc2.example.com:19389"
    _, client = answered(request)
    assert (client.server, client.port) == ("dc2.example.com", 19389)
