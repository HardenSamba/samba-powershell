"""A directory client that can write, so the write backend can be tested.

The supported samba-adws client exposes get_by_dn only; this fake adds the write
methods write_protocol.WriteClient defines, and records every call, so a test can
assert what the backend asked without a directory. A read-modify-write operation
reads through get_by_dn from a small recorded state.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


# Records every write and answers reads from a mutable in-memory object.
class FakeWriteClient:
    # Holds the endpoint, the recorded calls, and one object's current state.
    def __init__(self, server: str, port: int, timeout: float) -> None:
        self.server = server
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.state: dict[str, list[str]] = {
            "member": ["CN=Existing,DC=example,DC=com"],
            "userAccountControl": ["512"],
        }

    # Answers a read from the recorded state, only the asked-for attributes.
    def get_by_dn(self, identity: str, properties: Sequence[str] = ()) -> Mapping[str, object]:
        wanted = {name.lower() for name in properties}
        return {name: list(value) for name, value in self.state.items()
                if name.lower() in wanted}

    # Records a create.
    def create(self, identity: str, attributes: Mapping[str, Sequence[str]]) -> None:
        self.calls.append(("create", (identity, dict(attributes))))

    # Records a modify and applies it, so a second read reflects the change.
    def modify(self, identity: str, changes: Mapping[str, Sequence[str]]) -> None:
        self.calls.append(("modify", (identity, dict(changes))))
        for name, values in changes.items():
            self.state[name] = list(values)

    # Records a delete.
    def delete(self, identity: str) -> None:
        self.calls.append(("delete", (identity,)))

    # Records a password change, keeping the secret out of the call log's view
    # by recording only that it happened and for whom.
    def set_password(self, identity: str, password: str) -> None:
        self.calls.append(("set_password", (identity, "REDACTED")))

    # Records a rename.
    def rename(self, identity: str, new_dn: str) -> None:
        self.calls.append(("rename", (identity, new_dn)))
