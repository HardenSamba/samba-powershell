"""The directory-changing operations a write needs from the samba-adws client.

The supported client exposes get_by_dn only. These are the methods a write
command would call, named here so the backend can feature-detect their absence
and refuse cleanly rather than fail obscurely. The shapes map onto the server
handlers samba-adws already carries (create, modify, delete, set_password); what
is missing is the client surface, tracked for samba-adws to expose.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


# The write half of the directory client, as a structural type. A real client
# either implements every method or none; the backend checks per call.
class WriteClient(Protocol):
    # Creates one object at a distinguished name with the given attributes.
    def create(self, identity: str, attributes: Mapping[str, Sequence[str]]) -> None: ...

    # Replaces or clears the named attributes of one existing object.
    def modify(self, identity: str, changes: Mapping[str, Sequence[str]]) -> None: ...

    # Deletes one object by distinguished name.
    def delete(self, identity: str) -> None: ...

    # Sets an account's password, the secret carried in memory, never on a
    # command line: [MS-SAMR] stores unicodePwd as quoted UTF-16LE.
    def set_password(self, identity: str, password: str) -> None: ...

    # Moves or renames one object to a new distinguished name (an LDAP modrdn).
    def rename(self, identity: str, new_dn: str) -> None: ...
