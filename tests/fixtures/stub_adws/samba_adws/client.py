"""Stub ADWS search client that composes the real backend without a network."""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence

SCHEMA_NC = "CN=Schema,CN=Configuration,DC=example,DC=com"

# What the stub schema answers for: syntax OID and single-valued.
SCHEMA = {"userAccountControl": ("2.5.5.9", "true"), "adwsServer": ("2.5.5.12", "true"),
          "requestedCount": ("2.5.5.9", "true"), "memberOf": ("2.5.5.1", "false")}


# Mirrors the typed failure the supported client raises for a missing object.
class StubClientError(RuntimeError):
    # Carries the stable fields the backend maps onto an ErrorRecord.
    def __init__(self, message: str, code: str, category: str, target: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.target = target


# Mirrors samba_adws.search_query: the query is opaque to the backend.
def search_query(base: str, scope: str = "OneLevel", ldap_filter: str = "(objectClass=*)",
                 properties: Sequence[str] = ()) -> tuple[str, str, str, tuple[str, ...]]:
    return base, scope, ldap_filter, tuple(properties)


# Answers reads and searches from a fixed table instead of the ADWS endpoint.
class ADWSSearchClient:
    # Records the endpoint the backend selected.
    def __init__(self, server: str, port: int = 9389, timeout: float = 30.0) -> None:
        self.server = server
        self.port = port
        self.timeout = timeout

    # Returns one object, or raises the typed not-found failure, in the shapes a
    # directory answers with: an objectClass hierarchy, a non-ASCII value, one
    # memberOf, and the server echoed back so composition can see -Server arrive.
    def get_by_dn(self, identity: str,
                  properties: Sequence[str] = ()) -> Mapping[str, object]:
        if "missing" in identity.lower():
            raise StubClientError("Object not found: " + identity, "ObjectNotFound",
                                  "ObjectNotFound", identity)
        return {
            "distinguishedName": identity,
            "name": "Année",
            "objectClass": ("top", "person", "organizationalPerson", "user"),
            "userAccountControl": "512",
            "adwsServer": self.server,
            "requestedCount": str(len(list(properties))),
            "memberOf": "CN=Staff,DC=example,DC=com",
        }

    # Publishes the naming contexts the backend asks the RootDSE for.
    def naming_context(self, kind: str) -> str:
        return SCHEMA_NC if kind == "schemaNamingContext" else "DC=example,DC=com"

    # Answers schema lookups from the table, and resolves the one account name
    # the composition test uses.
    def search(self, query: tuple[str, str, str, tuple[str, ...]],
               count: int = 100) -> Generator[Mapping[str, object], None, None]:
        base, _, ldap_filter, _ = query
        if base == SCHEMA_NC:
            yield from ({"lDAPDisplayName": name, "attributeSyntax": syntax,
                         "isSingleValued": single, "systemFlags": "16"}
                        for name, (syntax, single) in SCHEMA.items()
                        if f"(lDAPDisplayName={name.lower()})" in ldap_filter)
        elif "(sAMAccountName=alice)" in ldap_filter:
            yield {"distinguishedName": "CN=Alice,DC=example,DC=com"}
