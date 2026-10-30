"""Opening an authenticated LDAP session on a domain controller."""

from __future__ import annotations

import socket

from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.ldap_api import LdapApi
from samba_powershell.ldap_binding import LdapBinding
from samba_powershell.ldap_directory import LdapDirectory

# How long a controller gets to accept the connection, apart from the time it
# gets to answer.
CONNECT_TIMEOUT = 10.0
# The SASL security the session must reach. A strength of 56 means encrypted. The
# buffer size is named too: the library merges these properties field by field,
# so a maxbufsize=0 from an ldaprc file would otherwise turn the layer off.
REQUIRED_PROTECTION = "minssf=56,maxbufsize=65536"
REQUIRED_STRENGTH = 56


# Opens a session authenticated with the caller's Kerberos ticket: the module
# holds no credential of its own and the directory applies the caller's rights.
# A controller that cannot be reached is asked about once more, for the reason.
def open_directory(api: LdapApi, server: str, port: int, timeout: float) -> DirectoryClient:
    connection = api.ldap.initialize(f"ldap://{server}:{port}")
    configure(connection, api, timeout)
    try:
        connection.sasl_interactive_bind_s("", api.sasl.gssapi(""))
    except api.ldap.SERVER_DOWN:
        probe(server, port)
        raise
    require_protection(connection, api)
    return LdapDirectory(connection, api)


# Sets the session up. Referrals are not chased: following one would bind to a
# server the caller did not name. NOCANON stops the LDAP library canonicalizing
# the name; Kerberos applies its own rules from krb5.conf after that.
def configure(connection: LdapBinding, api: LdapApi, timeout: float) -> None:
    connection.set_option(api.ldap.OPT_PROTOCOL_VERSION, api.ldap.VERSION3)
    connection.set_option(api.ldap.OPT_REFERRALS, 0)
    connection.set_option(api.ldap.OPT_X_SASL_NOCANON, 1)
    connection.set_option(api.ldap.OPT_X_SASL_SECPROPS, REQUIRED_PROTECTION)
    connection.set_option(api.ldap.OPT_NETWORK_TIMEOUT, min(timeout, CONNECT_TIMEOUT))
    connection.set_option(api.ldap.OPT_TIMEOUT, timeout)


# Refuses a session that ended up weaker than required, whatever a configuration
# file said. A bind with no security layer has no strength to read at all.
def require_protection(connection: LdapBinding, api: LdapApi) -> None:
    try:
        strength = connection.get_option(api.ldap.OPT_X_SASL_SSF)
    except ValueError:
        strength = 0
    if not isinstance(strength, int) or strength < REQUIRED_STRENGTH:
        raise OSError(f"SASL security layer too weak: strength {strength}")


# Connects once more without the library, which reports every network failure
# as "Can't contact LDAP server", so the operating system's reason is raised
# instead: a name that does not resolve, a refused port, a timeout.
def probe(server: str, port: int) -> None:
    with socket.create_connection((server, port), CONNECT_TIMEOUT):
        pass
