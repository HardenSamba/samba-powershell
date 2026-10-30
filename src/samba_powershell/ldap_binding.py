"""The part of a python-ldap connection that opens a session."""

from __future__ import annotations

from typing import Protocol


# ldap.ldapobject.LDAPObject as the session opener calls it, so it is typed
# without importing python-ldap before a command reaches the network.
class LdapBinding(Protocol):
    # Sets one option of the session.
    def set_option(self, option: int, value: object) -> None: ...

    # Reads one option of the session; raises ValueError when it has no value.
    def get_option(self, option: int) -> object: ...

    # Binds through SASL with the credentials the mechanism finds on its own.
    def sasl_interactive_bind_s(self, who: str, auth: object) -> None: ...
