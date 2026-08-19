"""The public entry point of the -Filter translator."""

from __future__ import annotations

from samba_powershell.adfilter.cursor import INVALID_FILTER, Cursor
from samba_powershell.adfilter.lexer import tokenize
from samba_powershell.adfilter.parser import parse_expression
from samba_powershell.errors import BackendError


# Translates one -Filter expression into the equivalent LDAP search filter.
def translate_filter(expression: str) -> str:
    tokens = tokenize(expression)
    if not tokens:
        raise BackendError(
            "The filter is empty.",
            INVALID_FILTER,
            "InvalidArgument",
        )
    cursor = Cursor(tokens)
    result = parse_expression(cursor)
    if cursor.index != len(cursor.tokens):
        trailing = cursor.tokens[cursor.index]
        raise BackendError(
            f"'{trailing.text}' stands after the end of the filter.",
            INVALID_FILTER,
            "InvalidArgument",
            trailing.text,
        )
    return result
