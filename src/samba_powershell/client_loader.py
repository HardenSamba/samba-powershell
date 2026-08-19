"""Lazy loading for the client API owned by samba-adws."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import cast

from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.errors import BackendError

ClientFactory = Callable[[str, int, float], DirectoryClient]


# Loads the optional samba-adws client only when a command reaches the network.
def load_client_factory() -> ClientFactory:
    try:
        module = importlib.import_module("samba_adws.client")
        candidate = getattr(module, "ADWSClient")
    except (ImportError, AttributeError) as exc:
        raise BackendError(
            "The samba-adws client API is not installed.",
            "SambaAD.ClientUnavailable",
            "ResourceUnavailable",
        ) from exc
    return cast(ClientFactory, candidate)
