"""The python-ldap modules this package reads the directory through."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# The three modules of python-ldap, imported together when a command first
# reaches the network and handed down, so the tests can replace all of them.
# Any is deliberate: python-ldap ships no type information.
@dataclass(frozen=True)
class LdapApi:
    ldap: Any
    sasl: Any
    controls: Any
