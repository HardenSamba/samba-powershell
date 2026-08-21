"""Stub of the samba-adws client package, importable without a directory.

Exports the read-only ADWSClient at package level, mirroring the real package.
It deliberately omits ADWSWriteClient, so a write through this stub exercises the
read-only fallback and refuses with SambaAD.WriteNotAvailable.
"""

from samba_adws.client import ADWSClient

__all__ = ("ADWSClient",)
