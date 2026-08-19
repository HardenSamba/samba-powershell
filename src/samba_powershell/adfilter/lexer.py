"""Splitting of a -Filter expression into tokens."""

from __future__ import annotations

from samba_powershell.adfilter.operators import OPERATOR_NAMES
from samba_powershell.adfilter.tokens import OPERATOR, PAREN, VALUE, WORD, Token
from samba_powershell.errors import BackendError

BREAK_CHARACTERS = frozenset(" \t\r\n()'\"")


# Splits one filter expression into the tokens the parser consumes.
def tokenize(expression: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    while index < len(expression):
        if expression[index].isspace():
            index += 1
            continue
        token, index = read_token(expression, index)
        tokens.append(token)
    return tokens


# Reads the single token starting at a non-space character.
def read_token(expression: str, index: int) -> tuple[Token, int]:
    character = expression[index]
    if character in "()":
        return Token(PAREN, character), index + 1
    if character in "'\"":
        return read_quoted(expression, index)
    return read_bare(expression, index)


# Reads a quoted value, treating a doubled quote as one literal character.
def read_quoted(expression: str, index: int) -> tuple[Token, int]:
    quote = expression[index]
    cursor = index + 1
    parts: list[str] = []
    while cursor < len(expression):
        if expression[cursor : cursor + 2] == quote * 2:
            parts.append(quote)
            cursor += 2
            continue
        if expression[cursor] == quote:
            return Token(VALUE, "".join(parts)), cursor + 1
        parts.append(expression[cursor])
        cursor += 1
    raise BackendError(
        "A quoted value in the filter is never closed.",
        "SambaAD.InvalidFilter",
        "InvalidArgument",
        expression,
    )


# Reads an unquoted word: an attribute, an operator, a number or a value.
def read_bare(expression: str, index: int) -> tuple[Token, int]:
    cursor = index
    while cursor < len(expression) and expression[cursor] not in BREAK_CHARACTERS:
        cursor += 1
    text = expression[index:cursor]
    kind = OPERATOR if text.lower() in OPERATOR_NAMES else WORD
    return Token(kind, text), cursor
