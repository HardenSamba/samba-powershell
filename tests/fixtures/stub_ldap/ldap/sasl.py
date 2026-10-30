"""Stub of ldap.sasl: the mechanism is opaque to the backend."""

from __future__ import annotations


# Names the mechanism, as ldap.sasl.gssapi does.
def gssapi(authorization_identity: str = "") -> object:
    return ("GSSAPI", authorization_identity)
