"""Bounded walk over the token list of one -Filter expression."""

from __future__ import annotations

from collections.abc import Sequence

from samba_powershell.adfilter.operators import COMPARISON_NAMES
from samba_powershell.adfilter.tokens import OPERATOR, PAREN, Token
from samba_powershell.errors import BackendError

INVALID_FILTER = "SambaAD.InvalidFilter"


# Reads tokens in order and never lets a parser run past the end.
class Cursor:
    # Starts at the first token of a tokenised filter expression.
    def __init__(self, tokens: Sequence[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    # Consumes the named logical operator when it comes next.
    def take_operator(self, name: str) -> bool:
        if self.index >= len(self.tokens):
            return False
        token = self.tokens[self.index]
        if token.kind != OPERATOR or token.text.lower() != name:
            return False
        self.index += 1
        return True

    # Consumes the given parenthesis when it comes next.
    def take_paren(self, character: str) -> bool:
        if self.index >= len(self.tokens):
            return False
        token = self.tokens[self.index]
        if token.kind != PAREN or token.text != character:
            return False
        self.index += 1
        return True

    # Consumes one comparison operator, naming whatever stands there instead.
    def take_comparison_operator(self) -> str:
        token = self.expect("an operator")
        if token.kind != OPERATOR or token.text.lower() not in COMPARISON_NAMES:
            raise BackendError(
                f"'{token.text}' is not a supported filter operator.",
                INVALID_FILTER,
                "InvalidArgument",
                token.text,
            )
        self.index += 1
        return token.text.lower()

    # Returns the next token unconsumed, refusing the kinds that cannot stand
    # there so an operator is never silently read as a literal value.
    def expect(self, expected: str, forbidden: tuple[str, ...] = ()) -> Token:
        if self.index >= len(self.tokens):
            raise BackendError(
                f"The filter ends where {expected} is expected.",
                INVALID_FILTER,
                "InvalidArgument",
            )
        token = self.tokens[self.index]
        if token.kind in forbidden:
            raise BackendError(
                f"'{token.text}' is not valid where {expected} is expected.",
                INVALID_FILTER,
                "InvalidArgument",
                token.text,
            )
        return token
