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
# The SD flags control of [MS-ADTS]: owner, group and DACL, encoded in BER. Without
# it a security descriptor is asked for whole, SACL included, and a caller who may
# not read the SACL gets no descriptor at all.
SD_FLAGS_OID = "1.2.840.113556.1.4.801"
SD_FLAGS_VALUE = b"\x30\x03\x02\x01\x07"


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

    # Reads one object by distinguished name or extended reference. An answer
    # with no entry is reported as missing; one with an entry and no attributes
    # is left for the class guard, as a later read may rightly find nothing new.
    def get_by_dn(self, identity: str, properties: Sequence[str] = ()) -> Mapping[str, object]:
        control = self._api.controls.RequestControl(SD_FLAGS_OID, False, SD_FLAGS_VALUE)
        found = self._connection.search_ext_s(identity, self._api.ldap.SCOPE_BASE, ANY_OBJECT,
                                              list(properties) or None, serverctrls=[control])
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
