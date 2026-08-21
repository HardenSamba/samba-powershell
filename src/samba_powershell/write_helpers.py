"""Small shared shapes the write operations build on."""

from __future__ import annotations

from collections.abc import Sequence

from samba_powershell import parameters


# The member distinguished name a membership change acts on.
def member_dn(request: dict[str, object]) -> str:
    from samba_powershell.guards import wire_identity

    return wire_identity(parameters.required_string(request, "member"))


# The member set with one entry added or removed, compared case-insensitively so
# a differently cased duplicate is not added a second time.
def with_member(present: Sequence[str], member: str, add: bool) -> list[str]:
    kept = [dn for dn in present if dn.lower() != member.lower()]
    return sorted(kept + [member]) if add else sorted(kept)


# Whether two member sets are the same, ignoring order and case.
def same_members(left: Sequence[str], right: Sequence[str]) -> bool:
    return sorted(dn.lower() for dn in left) == sorted(dn.lower() for dn in right)


# The write result one operation returns.
def result(identity: str, action: str) -> dict[str, object]:
    return {"type": "SambaAD.WriteResult",
            "properties": {"DistinguishedName": identity, "Action": action}}
