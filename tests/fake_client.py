"""Offline directory client used by backend tests."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence

DOMAIN = "DC=example,DC=com"
SCHEMA_NC = "CN=Schema,CN=Configuration,DC=example,DC=com"


# The binary objectSid a directory returns for one domain RID, MS-DTYP layout.
def sid_bytes(rid: int) -> bytes:
    parts = b"".join(n.to_bytes(4, "little") for n in (21, 1, 2, 3, rid))
    return bytes([1, 5]) + (5).to_bytes(6, "big") + parts


# The binary forms a directory actually returns: objectGUID as the mixed-endian
# GUID bytes, objectSid as the MS-DTYP structure. The fakes answer with these
# rather than friendly text, because the renderer is what the tests must prove.
ALICE_GUID = uuid.UUID("f81d4fae-7dec-11d0-a765-00a0c91e6bf6")
ALICE_SID = sid_bytes(1105)

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
    "logonCount": "7",
    "description": "Reads the ledgers",
    "isCriticalSystemObject": "false",
    "tokenGroups": (sid_bytes(513), sid_bytes(1301)),
    "msDS-KeyVersionNumber": "2",
    "info": "2026-01-01T10:00:00+00:00",
}

# Computed by the server only when named, as Samba computes msDS-KeyVersionNumber:
# a whole-object read leaves it out.
ON_REQUEST = frozenset({"msds-keyversionnumber"})

# A disabled account holding the bare minimum: no given name, no surname, no
# UPN, and a multi-valued attribute with a single value.
BOB = {
    "distinguishedName": "CN=Bob,CN=Users,DC=example,DC=com",
    "name": "Bob",
    "objectClass": ("top", "person", "organizationalPerson", "user"),
    "objectGUID": uuid.UUID("11111111-2222-3333-4444-555555555555").bytes_le,
    "sAMAccountName": "bob",
    "objectSid": sid_bytes(1106),
    "userAccountControl": "514",
    "memberOf": "CN=Sales,DC=example,DC=com",
}

# One security group with a single member, so the class guard has something to
# refuse and member's list shape has a case that matters.
SALES = {
    "distinguishedName": "CN=Sales,DC=example,DC=com",
    "name": "Sales",
    "objectClass": ("top", "group"),
    "objectGUID": uuid.UUID("0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0").bytes_le,
    "sAMAccountName": "sales",
    "objectSid": sid_bytes(1301),
    "groupType": "-2147483646",
    "member": "CN=Alice,CN=Users,DC=example,DC=com",
}

# A computer: a user by inheritance, which Get-ADUser must still refuse, and
# one with no dNSHostName, so the default set has a hole to fill.
PC01 = {
    "distinguishedName": "CN=PC01,CN=Computers,DC=example,DC=com",
    "name": "PC01",
    "objectClass": ("top", "person", "organizationalPerson", "user", "computer"),
    "objectGUID": uuid.UUID("22222222-3333-4444-5555-666666666666").bytes_le,
    "sAMAccountName": "PC01$",
    "objectSid": sid_bytes(1401),
    "userAccountControl": "4096",
    "servicePrincipalName": "HOST/pc01.example.com",
}

# Two accounts under one name, which no real directory should hold but an
# identity lookup must refuse rather than pick from.
TWIN_A = {"distinguishedName": "CN=Twin A,CN=Users,DC=example,DC=com", "name": "Twin A",
          "objectClass": ("top", "person", "organizationalPerson", "user"),
          "sAMAccountName": "twin"}
TWIN_B = {**TWIN_A, "distinguishedName": "CN=Twin B,CN=Users,DC=example,DC=com",
          "name": "Twin B"}

RECORDS = (ALICE, BOB, SALES, PC01, TWIN_A, TWIN_B)

# The schema entries the tests touch: syntax OID, single-valued, systemFlags.
SCHEMA = {
    "mail": ("2.5.5.12", True, "16"), "memberOf": ("2.5.5.1", False, "18"),
    "member": ("2.5.5.1", False, "16"), "userAccountControl": ("2.5.5.9", True, "16"),
    "logonCount": ("2.5.5.9", True, "16"), "whenCreated": ("2.5.5.11", True, "18"),
    "pwdLastSet": ("2.5.5.16", True, "16"), "accountExpires": ("2.5.5.16", True, "16"),
    "description": ("2.5.5.12", False, "16"), "sn": ("2.5.5.12", True, "16"),
    "objectSid": ("2.5.5.17", True, "18"), "groupType": ("2.5.5.9", True, "16"),
    "isCriticalSystemObject": ("2.5.5.8", True, "16"),
    "tokenGroups": ("2.5.5.17", False, "134217748"),
    "servicePrincipalName": ("2.5.5.12", False, "16"),
    "givenName": ("2.5.5.12", True, "16"), "name": ("2.5.5.12", True, "19"),
    "distinguishedName": ("2.5.5.1", True, "18"), "objectClass": ("2.5.5.2", False, "18"),
    "objectGUID": ("2.5.5.10", True, "18"), "sAMAccountName": ("2.5.5.12", True, "18"),
    "userPrincipalName": ("2.5.5.12", True, "16"),
    "msDS-KeyVersionNumber": ("2.5.5.9", True, "20"), "info": ("2.5.5.12", True, "16"),
}


# Mirrors the typed failure the supported client raises for a missing object.
class FakeNotFound(RuntimeError):
    # Carries the stable fields the backend maps onto an ErrorRecord.
    def __init__(self, identity: str) -> None:
        super().__init__(f"Object not found: {identity}")
        self.message = f"Object not found: {identity}"
        self.code = "ObjectNotFound"
        self.category = "ObjectNotFound"
        self.target = identity


# The record an identity names: by distinguished name, or by the extended
# <SID=...> and <GUID=...> forms the directory resolves on its own.
def record_for(identity: str) -> dict[str, object] | None:
    lowered = identity.lower()
    for record in RECORDS:
        if references(record, lowered):
            return record
    return None


# Whether one record answers to a lower-cased identity in any accepted form.
def references(record: dict[str, object], lowered: str) -> bool:
    if str(record["distinguishedName"]).lower() == lowered:
        return True
    guid = record.get("objectGUID")
    sid = record.get("objectSid")
    by_guid = isinstance(guid, bytes) and lowered == f"<guid={uuid.UUID(bytes_le=guid)}>"
    by_sid = isinstance(sid, bytes) and lowered == f"<sid={sid_text(sid).lower()}>"
    return by_guid or by_sid


# The textual form of a fake domain SID, the inverse of sid_bytes.
def sid_text(raw: bytes) -> str:
    rids = [int.from_bytes(raw[8 + 4 * n: 12 + 4 * n], "little") for n in range(raw[1])]
    return "S-1-5-" + "-".join(str(rid) for rid in rids)


# The schema entries a filter of (lDAPDisplayName=...) clauses asks for.
def schema_entries(ldap_filter: str) -> list[Mapping[str, object]]:
    wanted = {name.lower() for name in re.findall(r"lDAPDisplayName=([^)]+)", ldap_filter)}
    return [{"lDAPDisplayName": name, "attributeSyntax": syntax,
             "isSingleValued": "true" if single else "false", "systemFlags": flags}
            for name, (syntax, single, flags) in SCHEMA.items() if name.lower() in wanted]


# The records an account-name filter matches: the sAMAccountName clauses, the
# objectClass it requires and the classes it refuses with (!(objectClass=...)).
def account_matches(ldap_filter: str) -> list[Mapping[str, object]]:
    names = {name.lower() for name in re.findall(r"sAMAccountName=([^)]+)", ldap_filter)}
    refused = set(re.findall(r"\(!\(objectClass=([^)]+)\)\)", ldap_filter))
    required = set(re.findall(r"\(objectClass=([^)]+)\)", ldap_filter)) - refused
    found: list[Mapping[str, object]] = []
    for record in RECORDS:
        chain = {str(name) for name in tuple(record["objectClass"])}
        named = str(record["sAMAccountName"]).lower() in names
        if named and required <= chain and not refused & chain:
            found.append({"distinguishedName": record["distinguishedName"]})
    return found


# Supplies deterministic directory values without network access, and records
# what the backend asked for so a test can read it back.
class FakeClient:
    # Records the endpoint selected by the backend.
    def __init__(self, server: str, port: int, timeout: float) -> None:
        self.server = server
        self.port = port
        self.timeout = timeout
        self.requested: list[str] = []
        self.references: list[str] = []
        self.searches: list[tuple[str, str, str]] = []

    # Answers with the fetched subset of the record, the way a directory does:
    # only what was asked for, everything for an empty projection.
    def get_by_dn(self, identity: str,
                  properties: Sequence[str] = ()) -> Mapping[str, object]:
        self.requested = list(properties)
        self.references.append(identity)
        record = record_for(identity)
        if record is None:
            raise FakeNotFound(identity)
        wanted = {name.lower() for name in properties}
        found = {name: value for name, value in record.items()
                 if name.lower() in wanted or not (wanted or name.lower() in ON_REQUEST)}
        found["distinguishedName"] = record["distinguishedName"]
        return found

    # Publishes the two naming contexts the backend asks the RootDSE for.
    def naming_context(self, kind: str) -> str:
        return SCHEMA_NC if kind == "schemaNamingContext" else DOMAIN

    # Answers schema lookups and account-name lookups, at most limit of each.
    def search(self, base: str, scope: str, ldap_filter: str,
               properties: Sequence[str], limit: int) -> list[Mapping[str, object]]:
        self.searches.append((base, scope, ldap_filter))
        if base == SCHEMA_NC:
            return schema_entries(ldap_filter)[:limit]
        return account_matches(ldap_filter)[:limit]
