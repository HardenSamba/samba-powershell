"""Structural interface for the directory session the backend reads through."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


# The three directory questions the read cmdlets ask, in this module's terms
# rather than samba-adws's: read one object, name a naming context, and run a
# bounded search. The adapter over samba-adws and the offline fakes both meet it.
class DirectoryClient(Protocol):
    # Retrieves one object by distinguished name or extended reference; an
    # empty projection asks for every attribute the object holds.
    def get_by_dn(
        self,
        identity: str,
        properties: Sequence[str] = (),
    ) -> Mapping[str, object]: ...

    # Returns one naming context the RootDSE publishes, such as
    # defaultNamingContext or schemaNamingContext.
    def naming_context(self, kind: str) -> str: ...

    # Returns at most limit objects a search matches, so a caller that only
    # needs to know whether a match is unique never pulls a whole directory.
    def search(
        self,
        base: str,
        scope: str,
        ldap_filter: str,
        properties: Sequence[str],
        limit: int,
    ) -> list[Mapping[str, object]]: ...
