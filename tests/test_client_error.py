"""Tests for how a directory client failure reaches PowerShell."""

from __future__ import annotations

import pytest

from samba_powershell.client_error import translate_client_error
from samba_powershell.errors import BackendError

SERVER = "dc1.example.com"
IDENTITY = "CN=Alice,CN=Users,DC=example,DC=com"
NO_TICKET = ("SASL(-1): generic failure: GSSAPI Error: No credentials were supplied, or the "
             "credentials were unavailable or inaccessible (No Kerberos credentials "
             "available (default cache: FILE:/tmp/krb5cc_0))\x00")
NO_PRINCIPAL = ("SASL(-1): generic failure: GSSAPI Error: Unspecified GSS failure.  Minor code "
                "may provide more information (Server not found in Kerberos database)")


# Stands in for a python-ldap failure: all it says is one dictionary.
class LdapFailure(RuntimeError):
    # Stores the fields the way python-ldap does.
    def __init__(self, result: int, desc: str, info: str = "") -> None:
        super().__init__({"result": result, "desc": desc, "ctrls": [], "info": info})


# Translates one failure the way operations.get_object does.
def translated(error: Exception) -> BackendError:
    return translate_client_error(error, SERVER, IDENTITY)


# No ticket is an authentication failure against the server, says to run
# kinit, and loses the NUL the GSS status string ends with.
def test_no_ticket_names_kinit() -> None:
    error = translated(LdapFailure(-2, "Local error", NO_TICKET))
    assert (error.error_id, error.category, error.target) == (
        "SambaAD.TransportError", "AuthenticationError", SERVER)
    assert "kinit" in error.message
    assert "\x00" not in error.message


# "Server not found in Kerberos database" is an authentication failure, not a
# missing object, and the hint says why an IP address or an alias fails.
def test_an_unknown_principal_is_not_a_missing_object() -> None:
    error = translated(LdapFailure(-2, "Local error", NO_PRINCIPAL))
    assert error.category == "AuthenticationError"
    assert "DNS host name" in error.message
    assert SERVER in error.message


# A system without the Kerberos SASL plugin hears which package holds it.
def test_a_missing_sasl_plugin_names_the_package() -> None:
    error = translated(LdapFailure(-6, "Unknown authentication method",
                                   "SASL(-4): no mechanism available: No worthy mechs found"))
    assert error.category == "AuthenticationError"
    assert "libsasl2-modules-gssapi-mit" in error.message


# A session that cannot reach the required protection is refused, and says so.
def test_a_session_too_weak_to_encrypt_is_refused() -> None:
    error = translated(LdapFailure(-6, "Unknown authentication method",
                                   "SASL(-15): mechanism too weak for this user"))
    assert error.category == "AuthenticationError"
    assert "encrypted" in error.message


# Network failures are categorised by what failed, say which endpoint, and name
# the usual cause whichever way the resolver words a name that does not resolve.
@pytest.mark.parametrize(("failure", "category", "hint"), [
    (OSError(-2, "Name or service not known"), "ConnectionError", "does not resolve"),
    (OSError(-5, "No address associated with hostname"), "ConnectionError", "does not resolve"),
    (OSError(-3, "Temporary failure in name resolution"), "ConnectionError", "does not resolve"),
    (ConnectionRefusedError(111, "Connection refused"), "ConnectionError", "check the port"),
    (TimeoutError("timed out"), "OperationTimeout", ""),
    (LdapFailure(-5, "Timed out"), "OperationTimeout", ""),
    (LdapFailure(-1, "Can't contact LDAP server"), "ConnectionError", ""),
])
def test_network_failures_are_categorised(failure: Exception, category: str, hint: str) -> None:
    error = translated(failure)
    assert error.error_id == "SambaAD.TransportError"
    assert error.category == category
    assert error.message.startswith(f"Cannot reach the directory on '{SERVER}'")
    assert hint in error.message


# ldap.TIMEOUT arrives with no arguments at all, and is still a timeout.
def test_a_timeout_with_no_arguments_is_a_timeout() -> None:

    # Named the way python-ldap names it.
    class TIMEOUT(Exception):
        pass

    error = translated(TIMEOUT())
    assert (error.error_id, error.category, error.target) == (
        "SambaAD.TransportError", "OperationTimeout", SERVER)


# A failure that says nothing is still named, rather than reported as blank.
def test_a_silent_failure_is_named() -> None:

    # Carries no wording, as a few library exceptions do.
    class Silent(Exception):
        pass

    assert translated(Silent()).message == "Silent"


# A missing object is reported against the identity, in Windows's wording,
# whether the server said so, pointed elsewhere, or answered with nothing.
@pytest.mark.parametrize("failure", [
    LdapFailure(32, "No such object", "Base-DN '<SID=S-1-5-21-1-2-3-9>' not found"),
    LdapFailure(10, "Referral", "ldap://elsewhere/"),
    LookupError("<SID=S-1-5-21-1-2-3-9>"),
])
def test_a_missing_object_keeps_the_identity(failure: Exception) -> None:
    error = translated(failure)
    assert (error.target, error.category) == (IDENTITY, "ObjectNotFound")
    assert error.message == f"Cannot find an object with identity '{IDENTITY}'."


# What the directory refuses is reported against the identity, not the server.
@pytest.mark.parametrize(("failure", "error_id", "category"), [
    (LdapFailure(50, "Insufficient access"), "SambaAD.AccessDenied", "PermissionDenied"),
    (LdapFailure(34, "Invalid DN syntax"), "SambaAD.InvalidIdentity", "InvalidArgument"),
])
def test_refusals_keep_the_identity(failure: Exception, error_id: str, category: str) -> None:
    error = translated(failure)
    assert (error.error_id, error.category, error.target) == (error_id, category, IDENTITY)


# Any other failure keeps its wording, under one stable identifier.
def test_other_failures_pass_through() -> None:
    error = translated(LdapFailure(51, "Server is busy", "try later"))
    assert (error.error_id, error.category) == ("SambaAD.ClientFailure", "NotSpecified")
    assert error.message == "Server is busy: try later"
    assert translated(ValueError("The RootDSE publishes no x.")).message == (
        "The RootDSE publishes no x.")
