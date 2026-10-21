"""Tests for how a samba-adws client failure reaches PowerShell."""

from __future__ import annotations

import pytest

from samba_powershell.client_error import translate_client_error
from samba_powershell.errors import BackendError

SERVER = "dc1.example.com"
IDENTITY = "CN=Alice,CN=Users,DC=example,DC=com"
NO_TICKET = ("Major (458752): No credentials were supplied, or the credentials were "
             "unavailable or inaccessible, Minor (2529639053): No Kerberos credentials "
             "available (default cache: FILE:/tmp/krb5cc_0)\x00")
NO_PRINCIPAL = ("Major (851968): Unspecified GSS failure.  Minor code may provide more "
                "information, Minor (2529638919): Server not found in Kerberos database")


# Stands in for samba_adws.ADWSClientError, with the fields the backend reads.
class ClientFailure(RuntimeError):
    # Stores the typed fields the way the supported client does.
    def __init__(self, message: str, code: str, category: str, target: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.target = target


# Translates one failure the way operations.get_object does.
def translated(message: str, code: str, category: str = "ResourceUnavailable") -> BackendError:
    return translate_client_error(ClientFailure(message, code, category, IDENTITY),
                                  SERVER, IDENTITY)


# No ticket is an authentication failure against the server, says to run
# kinit, and loses the NUL the GSS status string ends with.
def test_no_ticket_names_kinit() -> None:
    error = translated(NO_TICKET, "TransportError")
    assert (error.error_id, error.category, error.target) == (
        "SambaAD.TransportError", "AuthenticationError", SERVER)
    assert "kinit" in error.message
    assert "\x00" not in error.message


# "Server not found in Kerberos database" is an authentication failure, not a
# missing object, whatever category samba-adws filed it under, and the hint
# says why an IP address or an alias fails.
def test_an_unknown_principal_is_not_a_missing_object() -> None:
    error = translated(NO_PRINCIPAL, "TransportError", "ObjectNotFound")
    assert error.category == "AuthenticationError"
    assert "DNS host name" in error.message
    assert SERVER in error.message


# Network failures are categorised by what failed, and say which endpoint.
@pytest.mark.parametrize(("message", "category"), [
    ("[Errno -2] Name or service not known", "ConnectionError"),
    ("[Errno 111] Connection refused", "ConnectionError"),
    ("timed out", "OperationTimeout"),
])
def test_network_failures_are_categorised(message: str, category: str) -> None:
    error = translated(message, "TransportError")
    assert error.category == category
    assert error.message.startswith(f"Cannot reach the ADWS endpoint on '{SERVER}'")


# A missing object is reported against the identity, in Windows's wording.
def test_a_missing_object_keeps_the_identity() -> None:
    error = translated("Object not found: <SID=S-1-5-21-1-2-3-9>", "ObjectNotFound",
                       "ObjectNotFound")
    assert (error.target, error.category) == (IDENTITY, "ObjectNotFound")
    assert error.message == f"Cannot find an object with identity '{IDENTITY}'."


# Any other client failure keeps its message, code and category.
def test_other_failures_pass_through() -> None:
    error = translated("Get response contains no attributes", "MalformedResponse",
                       "ProtocolError")
    assert (error.error_id, error.category) == ("SambaAD.MalformedResponse", "ProtocolError")
    assert error.message == "Get response contains no attributes"
