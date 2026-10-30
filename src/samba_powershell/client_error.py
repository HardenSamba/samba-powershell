"""Translation of directory client failures into backend errors."""

from __future__ import annotations

import re

from samba_powershell.errors import BackendError
from samba_powershell.guards import not_found

CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")

# The LDAP result codes of RFC 4511, and the negative ones the OpenLDAP library
# adds for what never reached a server, that say something the caller can use.
NO_SUCH_OBJECT = 32
REFERRAL = 10
INVALID_DN_SYNTAX = 34
INSUFFICIENT_ACCESS = 50
TIMED_OUT = -5
MISSING = {NO_SUCH_OBJECT, REFERRAL}
# Server down, local error, encoding, decoding, timeout, unknown authentication
# method, connect error; then the bind refusals a server can answer with.
TRANSPORT = {-1, -2, -3, -4, -5, -6, -11, 7, 8, 48, 49}

# What usually lies behind a transport failure, keyed by a phrase of the
# underlying message, worded as what the operator can do about it.
HINTS = (
    ("no credentials", " Obtain a Kerberos ticket with kinit, from the Debian package "
     "krb5-user, or point KRB5CCNAME at a cache that holds one."),
    ("server not found in kerberos database", " -Server must be the domain controller's "
     "DNS host name: Kerberos authenticates ldap/<name>, and an IP address or an alias "
     "usually has no such principal."),
    ("no worthy mechs", " Kerberos is not available to LDAP here; install the Debian package "
     "libsasl2-modules-gssapi-mit."),
    ("too weak", " The session could not be encrypted, and the cmdlets refuse to read the "
     "directory without that."),
    ("name or service not known", " The name does not resolve; check -Server."),
    ("no address associated with hostname", " The name does not resolve; check -Server."),
    ("failure in name resolution", " The name does not resolve; check -Server."),
    ("connection refused", " Nothing listens on that port; check the port in -Server, "
     "or whether the domain controller runs."),
)


# Reports a transport failure against the server with its cause named, and
# anything else against the identity the caller gave rather than the reference
# the backend sent for it.
def translate_client_error(error: Exception, server: str, identity: str) -> BackendError:
    result, text = ldap_failure(error)
    message = CONTROL.sub(" ", text).strip()
    if isinstance(error, LookupError) or result in MISSING:
        return not_found(identity)
    if isinstance(error, OSError) or result in TRANSPORT:
        return BackendError(transport_message(message, server), "SambaAD.TransportError",
                            transport_category(message), server)
    if result == INSUFFICIENT_ACCESS:
        return BackendError(message, "SambaAD.AccessDenied", "PermissionDenied", identity)
    if result == INVALID_DN_SYNTAX:
        return BackendError(message, "SambaAD.InvalidIdentity", "InvalidArgument", identity)
    return BackendError(message or type(error).__name__, "SambaAD.ClientFailure",
                        "NotSpecified", identity)


# The result code and the wording of a python-ldap failure, which arrive as a
# dictionary in its first argument; any other exception has only its text. A
# timeout waiting for an answer is the exception: ldap.TIMEOUT says nothing at all.
def ldap_failure(error: Exception) -> tuple[int | None, str]:
    if not error.args and type(error).__name__ == "TIMEOUT":
        return TIMED_OUT, "timed out"
    details = error.args[0] if error.args else None
    if not isinstance(details, dict):
        return None, str(error)
    wording = [details.get("desc"), details.get("info")]
    result = details.get("result")
    return (result if isinstance(result, int) else None,
            ": ".join(str(part) for part in wording if part))


# The category of a transport failure, decided from what the system said.
def transport_category(message: str) -> str:
    lowered = message.lower()
    if any(word in lowered for word in ("sasl", "gssapi", "kerberos", "credentials")):
        return "AuthenticationError"
    if "timed out" in lowered:
        return "OperationTimeout"
    return "ConnectionError"


# A transport failure as an operator can act on it: which endpoint, what the
# system said, and what usually causes it.
def transport_message(message: str, server: str) -> str:
    lowered = message.lower()
    hint = next((text for phrase, text in HINTS if phrase in lowered), "")
    return f"Cannot reach the directory on '{server}': {message.rstrip('.')}.{hint}"
