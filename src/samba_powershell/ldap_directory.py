"""The directory session the backend reads through, over LDAP."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from samba_powershell.ldap_api import LdapApi
from samba_powershell.ldap_paging import paged_entries
from samba_powershell.ldap_protocol import LdapConnection
from samba_powershell.ldap_values import BINARY_SYNTAXES, decoded_entry

ANY_OBJECT = "(objectClass=*)"
SCOPES = {"Base": "SCOPE_BASE", "OneLevel": "SCOPE_ONELEVEL", "Subtree": "SCOPE_SUBTREE"}
# Far more than any schema defines; only a bound on a question that has one.
SCHEMA_LIMIT = 100000


# Adapts one bound python-ldap connection to DirectoryClient. The naming
# contexts and the binary attributes each cost one search the first time and
# none after: neither changes while one cmdlet call runs.
class LdapDirectory:
    # Holds the bound connection and the library it came from.
    def __init__(self, connection: LdapConnection, api: LdapApi) -> None:
        self._connection = connection
        self._api = api
        self._contexts: dict[str, str] = {}
        self._binary: frozenset[str] | None = None

    # Reads one object by distinguished name or extended reference. An object
    # the caller may not see answers with nothing, which is reported as missing.
    def get_by_dn(self, identity: str, properties: Sequence[str] = ()) -> Mapping[str, object]:
        found = self._connection.search_ext_s(identity, self._api.ldap.SCOPE_BASE, ANY_OBJECT,
                                              list(properties) or None)
        entries = [entry for entry in found if entry[0] is not None]
        if not entries:
            raise LookupError(identity)
        return decoded_entry(str(entries[0][0]), entries[0][1], self._binary_names())

    # Returns one naming context, asking the RootDSE only the first time.
    def naming_context(self, kind: str) -> str:
        if kind not in self._contexts:
            found = self._connection.search_ext_s("", self._api.ldap.SCOPE_BASE, ANY_OBJECT,
                                                  [kind])
            values = found[0][1].get(kind) if found else None
            if not values:
                raise ValueError(f"The RootDSE publishes no {kind}.")
            self._contexts[kind] = values[0].decode("utf-8")
        return self._contexts[kind]

    # Returns at most limit objects a search matches.
    def search(self, base: str, scope: str, ldap_filter: str,
               properties: Sequence[str], limit: int) -> list[Mapping[str, object]]:
        found = paged_entries(self._connection, self._api, base,
                              getattr(self._api.ldap, SCOPES[scope]), ldap_filter,
                              list(properties) or None, limit)
        binary = self._binary_names()
        return [decoded_entry(str(dn), attributes, binary) for dn, attributes in found]

    # The lower-case names of the attributes whose values are not text, from the
    # directory's own schema, so an extended schema decodes correctly too.
    def _binary_names(self) -> frozenset[str]:
        if self._binary is None:
            clauses = "".join(f"(attributeSyntax={oid})" for oid in BINARY_SYNTAXES)
            found = paged_entries(
                self._connection, self._api, self.naming_context("schemaNamingContext"),
                self._api.ldap.SCOPE_ONELEVEL, f"(&(objectClass=attributeSchema)(|{clauses}))",
                ["lDAPDisplayName"], SCHEMA_LIMIT)
            self._binary = frozenset(value.decode("utf-8").lower() for _, attributes in found
                                     for value in attributes.get("lDAPDisplayName", ()))
        return self._binary
