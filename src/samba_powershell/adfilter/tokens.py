"""Lexical units produced by the -Filter lexer."""

from __future__ import annotations

from typing import NamedTuple

WORD = "word"
VALUE = "value"
OPERATOR = "operator"
PAREN = "paren"


# Carries one lexical unit of a -Filter expression.
class Token(NamedTuple):
    kind: str
    text: str
