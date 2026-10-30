"""The part of a python-ldap connection that reads the directory."""

from __future__ import annotations

from typing import Protocol

# One entry as python-ldap answers it: the DN, None for a search reference, and
# every attribute's raw values.
RawEntry = tuple[str | None, dict[str, list[bytes]]]


# ldap.ldapobject.LDAPObject as the adapter reads through it, so the adapter is
# typed without importing python-ldap before a command reaches the network.
class LdapConnection(Protocol):
    # Runs one search and waits for all of its answer.
    def search_ext_s(self, base: str, scope: int, filterstr: str, attrlist: list[str] | None,
                     serverctrls: list[object] | None = None) -> list[RawEntry]: ...

    # Starts one search carrying server controls, and returns its message id.
    def search_ext(self, base: str, scope: int, filterstr: str, attrlist: list[str] | None,
                   serverctrls: list[object]) -> int: ...

    # Waits for the answer to one search: type, entries, message id, controls.
    def result3(self, msgid: int) -> tuple[int, list[RawEntry], int, list[object]]: ...
