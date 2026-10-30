"""Lazy loading for the LDAP client library."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import partial

from samba_powershell.client_protocol import DirectoryClient
from samba_powershell.errors import BackendError
from samba_powershell.ldap_api import LdapApi
from samba_powershell.ldap_session import open_directory

ClientFactory = Callable[[str, int, float], DirectoryClient]


# Loads python-ldap only when a command reaches the network. A module installed
# from the PowerShell Gallery cannot pull a Debian package in, so this is where
# a system without one learns what to install.
def load_client_factory() -> ClientFactory:
    try:
        api = LdapApi(importlib.import_module("ldap"), importlib.import_module("ldap.sasl"),
                      importlib.import_module("ldap.controls"))
    except ImportError as exc:
        raise BackendError(
            "The LDAP client library is not installed. Install the Debian packages "
            "python3-ldap and libsasl2-modules-gssapi-mit.",
            "SambaAD.ClientUnavailable",
            "ResourceUnavailable",
        ) from exc
    return partial(open_directory, api)
