"""Directory values in the shapes the renderer reads: text, bytes and tuples."""

from __future__ import annotations

from collections.abc import Collection

# The attributeSyntax OIDs of [MS-ADTS] whose values are not text: octet
# string, security descriptor and SID.
BINARY_SYNTAXES = ("2.5.5.10", "2.5.5.15", "2.5.5.17")


# One entry with its values decoded, and its distinguished name present whether
# or not the read named it: the renderer and the class guard both expect it.
def decoded_entry(dn: str, attributes: dict[str, list[bytes]],
                  binary: Collection[str]) -> dict[str, object]:
    entry = {name: shaped(name, values, binary) for name, values in attributes.items()}
    if not any(name.lower() == "distinguishedname" for name in entry):
        entry["distinguishedName"] = dn
    return entry


# One attribute as one value, or as a tuple when it holds several.
def shaped(name: str, values: list[bytes], binary: Collection[str]) -> object:
    items = tuple(decoded_value(value, name.lower() in binary) for value in values)
    return items[0] if len(items) == 1 else items


# One value as text, unless the schema says it is binary. Trying to decode would
# not tell them apart: S-1-5-32-544 as a binary SID is valid UTF-8. Text that is
# not UTF-8 stays bytes rather than failing the whole read.
def decoded_value(value: bytes, binary: bool) -> str | bytes:
    if binary:
        return value
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value
