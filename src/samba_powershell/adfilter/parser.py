"""Recursive descent over the -Filter grammar, emitting LDAP directly."""

from __future__ import annotations

import re

from samba_powershell.adfilter.comparison import build_comparison
from samba_powershell.adfilter.cursor import INVALID_FILTER, Cursor
from samba_powershell.adfilter.tokens import OPERATOR, PAREN
from samba_powershell.errors import BackendError

# RFC 4512 spells an attribute description as a letter then letters, digits
# and hyphens. Anything else would be interpolated into the filter unchecked.
ATTRIBUTE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


# Parses the lowest-precedence level, joining -and groups with -or.
def parse_expression(cursor: Cursor) -> str:
    parts = [parse_and(cursor)]
    while cursor.take_operator("-or"):
        parts.append(parse_and(cursor))
    if len(parts) == 1:
        return parts[0]
    return "(|" + "".join(parts) + ")"


# Parses -and, which binds tighter than -or and looser than -not.
def parse_and(cursor: Cursor) -> str:
    parts = [parse_not(cursor)]
    while cursor.take_operator("-and"):
        parts.append(parse_not(cursor))
    if len(parts) == 1:
        return parts[0]
    return "(&" + "".join(parts) + ")"


# Parses -not, which binds tighter than every binary operator.
def parse_not(cursor: Cursor) -> str:
    if cursor.take_operator("-not"):
        return "(!" + parse_not(cursor) + ")"
    return parse_primary(cursor)


# Parses a parenthesised group, or falls through to a single comparison.
def parse_primary(cursor: Cursor) -> str:
    if not cursor.take_paren("("):
        return parse_comparison(cursor)
    inner = parse_expression(cursor)
    if not cursor.take_paren(")"):
        raise BackendError(
            "A group in the filter is never closed.",
            INVALID_FILTER,
            "InvalidArgument",
        )
    return inner


# Parses one comparison, refusing an attribute name it cannot vouch for.
def parse_comparison(cursor: Cursor) -> str:
    attribute = cursor.expect("an attribute name", (OPERATOR, PAREN))
    if not ATTRIBUTE_NAME.fullmatch(attribute.text):
        raise BackendError(
            f"'{attribute.text}' is not a valid attribute name.",
            INVALID_FILTER,
            "InvalidArgument",
            attribute.text,
        )
    cursor.index += 1
    operator = cursor.take_comparison_operator()
    value = cursor.expect("a value", (OPERATOR, PAREN))
    cursor.index += 1
    return build_comparison(attribute.text, operator, value)
