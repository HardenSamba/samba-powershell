"""Performing a directory-changing operation, or refusing it cleanly."""

from __future__ import annotations

from samba_powershell.client_error import translate_client_error
from samba_powershell.client_loader import ClientFactory
from samba_powershell.errors import BackendError

ADWS_PORT = 9389
ADWS_TIMEOUT = 30.0
# The client methods a write needs. The supported client has none of them yet,
# so a write refuses by name rather than mutating nothing and reporting success.
WRITE_METHODS = ("create", "modify", "delete", "set_password", "rename")


# The reason a client cannot perform a write, as this module's own error.
def _unavailable(method: str) -> BackendError:
    return BackendError(
        f"The samba-adws client cannot {method}: it exposes read access only. "
        "Writing needs a client operation samba-adws does not offer yet, and the "
        "authorization fix tracked in samba-adws#8. See docs/writing.md.",
        "SambaAD.WriteNotAvailable", "NotImplemented", method)


# The client, refused unless it can actually perform the write asked of it.
def writable_client(client_factory: ClientFactory, server: str, method: str) -> object:
    client = client_factory(server, ADWS_PORT, ADWS_TIMEOUT)
    if not callable(getattr(client, method, None)):
        raise _unavailable(method)
    return client


# Calls one write method on a client already opened, turning a client fault into
# a backend error. Used when a read had to happen on the same client first.
def call_on(client: object, method: str, *args: object) -> None:
    if not callable(getattr(client, method, None)):
        raise _unavailable(method)
    try:
        getattr(client, method)(*args)
    except BackendError:
        raise
    except Exception as exc:
        raise translate_client_error(exc) from exc


# Opens the client and runs one write, refusing if it cannot perform it.
def perform(client_factory: ClientFactory, server: str, method: str, *args: object) -> None:
    call_on(writable_client(client_factory, server, method), method, *args)
