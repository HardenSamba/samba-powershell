"""Lazy loading for the client API owned by samba-adws."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import partial
from typing import cast

from samba_powershell.adws_directory import AdwsDirectory
from samba_powershell.adws_protocol import AdwsSearchClient, QueryFactory
from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.errors import BackendError

ClientFactory = Callable[[str, int, float], DirectoryClient]
SearchClientType = Callable[[str, int, float], AdwsSearchClient]


# Loads samba-adws only when a command reaches the network. The search client
# is what resolves account names and reads the schema; samba-adws has carried
# it since its first packaged release, 1.0.0.
def load_client_factory() -> ClientFactory:
    try:
        module = importlib.import_module("samba_adws")
        client_type = cast(SearchClientType, getattr(module, "ADWSSearchClient"))
        query = cast(QueryFactory, getattr(module, "search_query"))
    except (ImportError, AttributeError) as exc:
        raise BackendError(
            "The samba-adws client API is not installed, or predates the search client "
            "this module needs (samba-adws 1.0.0 or later).",
            "SambaAD.ClientUnavailable",
            "ResourceUnavailable",
        ) from exc
    return partial(open_directory, client_type, query)


# Opens one directory session on the samba-adws search client.
def open_directory(client_type: SearchClientType, query: QueryFactory,
                   server: str, port: int, timeout: float) -> DirectoryClient:
    return AdwsDirectory(client_type(server, port, timeout), query)
