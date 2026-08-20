"""Offline directory client used by backend tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


# Supplies deterministic directory values without network access.
class FakeClient:
    # Records the endpoint selected by the backend.
    def __init__(self, server: str, port: int, timeout: float) -> None:
        self.server = server
        self.port = port
        self.timeout = timeout

    # Returns one typed test object for the requested distinguished name.
    def get_by_dn(
        self,
        identity: str,
        properties: Sequence[str] = (),
    ) -> Mapping[str, object]:
        return {
            "DistinguishedName": identity,
            "Name": "Alice",
            "RequestedProperties": list(properties),
        }
