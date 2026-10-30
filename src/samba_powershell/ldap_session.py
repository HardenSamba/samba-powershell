"""Opening an authenticated LDAP session on a domain controller."""

from __future__ import annotations

import socket

from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.ldap_api import LdapApi
from samba_powershell.ldap_directory import LdapDirectory
from samba_powershell.ldap_protocol import LdapConnection

# How long a controller gets to accept the connection, apart from the time it
# gets to answer.
CONNECT_TIMEOUT = 10.0
# The SASL security strength the session must reach, or the bind fails. 56 means
# encrypted, so directory data never crosses the network in clear; Kerberos
# through GSSAPI reaches it on its own, and this refuses a downgrade.
REQUIRED_PROTECTION = "minssf=56"


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
    return LdapDirectory(connection, api)


# Sets the session up. Referrals are not chased: following one would bind to a
# server the caller did not name. NOCANON keeps Kerberos on the name the caller
# gave, rather than on whatever reverse DNS says it is.
def configure(connection: LdapConnection, api: LdapApi, timeout: float) -> None:
    connection.set_option(api.ldap.OPT_PROTOCOL_VERSION, api.ldap.VERSION3)
    connection.set_option(api.ldap.OPT_REFERRALS, 0)
    connection.set_option(api.ldap.OPT_X_SASL_NOCANON, 1)
    connection.set_option(api.ldap.OPT_X_SASL_SECPROPS, REQUIRED_PROTECTION)
    connection.set_option(api.ldap.OPT_NETWORK_TIMEOUT, min(timeout, CONNECT_TIMEOUT))
    connection.set_option(api.ldap.OPT_TIMEOUT, timeout)


# Connects once more without the library, which reports every network failure
# as "Can't contact LDAP server", so the operating system's reason is raised
# instead: a name that does not resolve, a refused port, a timeout.
def probe(server: str, port: int) -> None:
    with socket.create_connection((server, port), CONNECT_TIMEOUT):
        pass
