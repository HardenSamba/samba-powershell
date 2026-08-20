"""Structural interface for the client supplied by samba-adws."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


# Defines the only samba-adws client operation needed by the architecture proof.
class DirectoryClient(Protocol):
    # Retrieves one directory object by distinguished name.
    def get_by_dn(
        self,
        identity: str,
        properties: Sequence[str] = (),
    ) -> Mapping[str, object]: ...
