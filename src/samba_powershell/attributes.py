"""Reading an attribute out of a directory answer, whatever case the server used."""

from __future__ import annotations

from collections.abc import Mapping


# The value of one attribute, found without regard to the server's casing:
# LDAP attribute names have no case, and the server answers in its own.
def find(attributes: Mapping[str, object], name: str) -> object:
    wanted = name.lower()
    for key, value in attributes.items():
        if key.lower() == wanted:
            return value
    return None


# Every value one attribute holds, as a tuple whether it holds one or many.
def values_of(attributes: Mapping[str, object], name: str) -> tuple[object, ...]:
    value = find(attributes, name)
    if value is None:
        return ()
    return value if isinstance(value, tuple) else (value,)
