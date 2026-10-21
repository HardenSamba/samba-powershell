"""The part of the samba-adws search client this module relies on."""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from typing import Protocol

# samba_adws.search_query: base, scope, filter and projection in, a validated
# query out. The query is opaque here; it only travels back to search().
QueryFactory = Callable[[str, str, str, Sequence[str]], object]


# samba_adws.ADWSSearchClient as this module calls it, so the adapter is typed
# without importing samba-adws before a command reaches the network.
class AdwsSearchClient(Protocol):
    # Reads one object, as samba_adws.ADWSClient.get_by_dn does.
    def get_by_dn(
        self, identity: str, properties: Sequence[str] = ()
    ) -> Mapping[str, object]: ...

    # Names one naming context from the RootDSE.
    def naming_context(self, kind: str) -> str: ...

    # Yields every object a query matches, holding one connection meanwhile.
    def search(
        self, query: object, count: int
    ) -> Generator[Mapping[str, object], None, None]: ...
