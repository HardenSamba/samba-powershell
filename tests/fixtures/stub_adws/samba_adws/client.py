"""Stub ADWS client that composes the real backend without a network."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


# Mirrors the typed failure the supported client raises for a missing object.
class StubClientError(RuntimeError):
    # Carries the stable fields the backend maps onto an ErrorRecord.
    def __init__(self, message: str, code: str, category: str, target: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.category = category
        self.target = target


# Answers reads from a fixed table instead of the ADWS endpoint.
class ADWSClient:
    # Records the endpoint the backend selected.
    def __init__(self, server: str, port: int = 9389, timeout: float = 30.0) -> None:
        self.server = server
        self.port = port
        self.timeout = timeout

    # Returns one object, or raises the typed not-found failure. The answer
    # carries the shapes a directory answers with: an objectClass hierarchy,
    # a non-ASCII value to prove the UTF-8 boundary, and the server echoed
    # back so composition can see -Server arrive.
    def get_by_dn(
        self,
        identity: str,
        properties: Sequence[str] = (),
    ) -> Mapping[str, object]:
        if "missing" in identity.lower():
            raise StubClientError(
                "The directory object was not found.",
                "ObjectNotFound",
                "ObjectNotFound",
                identity,
            )
        return {
            "distinguishedName": identity,
            "name": "Année",
            "objectClass": ("top", "person", "organizationalPerson", "user"),
            "userAccountControl": "512",
            "adwsServer": self.server,
            "requestedCount": str(len(list(properties))),
        }
