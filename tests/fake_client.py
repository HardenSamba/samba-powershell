"""Offline directory client used by backend tests."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

# The binary forms a directory actually returns: objectGUID as the mixed-endian
# GUID bytes, objectSid as the MS-DTYP structure. The fakes answer with these
# rather than friendly text, because the renderer is what the tests must prove.
ALICE_GUID = uuid.UUID("f81d4fae-7dec-11d0-a765-00a0c91e6bf6")
ALICE_SID = bytes([1, 5]) + (5).to_bytes(6, "big") + b"".join(
    n.to_bytes(4, "little") for n in (21, 1, 2, 3, 1105))

# What the recorded directory holds for the one account the tests read.
ALICE = {
    "distinguishedName": "CN=Alice,CN=Users,DC=example,DC=com",
    "givenName": "Alice",
    "name": "Alice",
    "objectClass": ("top", "person", "organizationalPerson", "user"),
    "objectGUID": ALICE_GUID.bytes_le,
    "sAMAccountName": "alice",
    "objectSid": ALICE_SID,
    "sn": "Liddell",
    "userPrincipalName": "alice@example.com",
    "userAccountControl": "512",
    "whenCreated": "20240229120000.0Z",
    "pwdLastSet": "133528896000000000",
    "accountExpires": "0",
    "mail": "alice@example.com",
    "memberOf": ("CN=Sales,DC=example,DC=com", "CN=Staff,DC=example,DC=com"),
}

# And one security group, so the class guard has something to refuse.
SALES = {
    "distinguishedName": "CN=Sales,DC=example,DC=com",
    "name": "Sales",
    "objectClass": ("top", "group"),
    "objectGUID": uuid.UUID("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0").bytes_le,
    "sAMAccountName": "sales",
    "objectSid": bytes([1, 5]) + (5).to_bytes(6, "big") + b"".join(
        n.to_bytes(4, "little") for n in (21, 1, 2, 3, 1301)),
    "groupType": "-2147483646",
}


# Supplies deterministic directory values without network access.
class FakeClient:
    # Records the endpoint selected by the backend.
    def __init__(self, server: str, port: int, timeout: float) -> None:
        self.server = server
        self.port = port
        self.timeout = timeout
        self.requested: list[str] = []

    # Answers with the fetched subset of the recorded account, the way a
    # directory does: only what was asked for, under the server's spellings.
    def get_by_dn(
        self,
        identity: str,
        properties: Sequence[str] = (),
    ) -> Mapping[str, object]:
        self.requested = list(properties)
        record = SALES if "sales" in identity.lower() else ALICE
        wanted = {name.lower() for name in properties}
        found = {name: value for name, value in record.items() if name.lower() in wanted}
        found["distinguishedName"] = identity
        return found
