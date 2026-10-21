"""The directory session the backend reads through, over the samba-adws client."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import islice

from samba_powershell.adws_protocol import AdwsSearchClient, QueryFactory

# The most one Pull may carry, per samba-adws's own page-size ceiling.
MAX_PAGE_SIZE = 1000


# Adapts one samba-adws search client to DirectoryClient. Each naming context
# costs one RootDSE read the first time a session asks for that kind, and none
# after: the RootDSE does not change while one cmdlet call runs.
class AdwsDirectory:
    # Holds the client and the query builder that validates its searches.
    def __init__(self, client: AdwsSearchClient, query: QueryFactory) -> None:
        self._client = client
        self._query = query
        self._contexts: dict[str, str] = {}

    # Reads one object through the supported client.
    def get_by_dn(self, identity: str, properties: Sequence[str] = ()) -> Mapping[str, object]:
        return self._client.get_by_dn(identity, properties)

    # Returns one naming context, asking the RootDSE only the first time.
    def naming_context(self, kind: str) -> str:
        if kind not in self._contexts:
            self._contexts[kind] = self._client.naming_context(kind)
        return self._contexts[kind]

    # Collects at most limit matches, then closes the enumeration, which gives
    # back the connection samba-adws held open for it.
    def search(self, base: str, scope: str, ldap_filter: str,
               properties: Sequence[str], limit: int) -> list[Mapping[str, object]]:
        query = self._query(base, scope, ldap_filter, properties)
        matches = self._client.search(query, min(max(limit, 1), MAX_PAGE_SIZE))
        try:
            return [dict(item) for item in islice(matches, limit)]
        finally:
            matches.close()
