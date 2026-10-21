"""Translation of samba-adws client failures into backend errors."""

from __future__ import annotations

import re

from samba_powershell.errors import BackendError
from samba_powershell.guards import not_found

CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")

# What usually lies behind a transport failure, keyed by a phrase of the
# underlying message, worded as what the operator can do about it.
HINTS = (
    ("no credentials", " Obtain a Kerberos ticket with kinit, or point KRB5CCNAME at a "
     "cache that holds one."),
    ("server not found in kerberos database", " -Server must be the domain controller's "
     "DNS host name: Kerberos authenticates host/<name>, so an IP address or an alias has "
     "no principal to authenticate."),
    ("name or service not known", " The name does not resolve; check -Server."),
    ("no address associated with hostname", " The name does not resolve; check -Server."),
    ("failure in name resolution", " The name does not resolve; check -Server."),
    ("connection refused", " Nothing listens on that port; check the port in -Server, "
     "or whether samba-adws runs."),
)


# Preserves the client's typed fields: a transport failure is reported against
# the server with its cause named, anything else against the identity the caller
# gave rather than the reference the backend sent for it.
def translate_client_error(error: Exception, server: str, identity: str) -> BackendError:
    message = CONTROL.sub(" ", text_field(error, "message", str(error))).strip()
    code = text_field(error, "code", "ClientFailure")
    error_id = code if code.startswith("SambaAD.") else f"SambaAD.{code}"
    if code == "TransportError":
        return BackendError(transport_message(message, server), error_id,
                            transport_category(message), server)
    category = text_field(error, "category", "NotSpecified")
    if category == "ObjectNotFound":
        return not_found(identity)
    return BackendError(message, error_id, category, identity)


# One string field of a client error, or the fallback when it is absent or not text.
def text_field(error: Exception, name: str, fallback: str) -> str:
    value: object = getattr(error, name, fallback)
    return value if isinstance(value, str) and value else fallback


# The category a transport failure belongs to. samba-adws files any message
# containing "not found" under ObjectNotFound, Kerberos's "Server not found in
# Kerberos database" included, so the category is decided here from the code.
def transport_category(message: str) -> str:
    lowered = message.lower()
    if "major (" in lowered or "kerberos" in lowered or "credentials" in lowered:
        return "AuthenticationError"
    if "timed out" in lowered:
        return "OperationTimeout"
    return "ConnectionError"


# A transport failure as an operator can act on it: which endpoint, what the
# system said, and what usually causes it.
def transport_message(message: str, server: str) -> str:
    lowered = message.lower()
    hint = next((text for phrase, text in HINTS if phrase in lowered), "")
    return f"Cannot reach the ADWS endpoint on '{server}': {message.rstrip('.')}.{hint}"
