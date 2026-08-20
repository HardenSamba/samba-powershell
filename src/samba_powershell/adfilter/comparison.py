"""Rendering of one attribute/operator/value triple as an LDAP assertion."""

from __future__ import annotations

from samba_powershell.adfilter.operators import (
    MATCHING_RULES,
    NULL_FORMS,
    PATTERN_FORMS,
    SIMPLE_FORMS,
)
from samba_powershell.adfilter.tokens import WORD, Token
from samba_powershell.errors import BackendError
from samba_powershell.ldap_escape import escape_pattern, escape_value

INVALID_FILTER = "SambaAD.InvalidFilter"


# Renders one comparison, routing on the operator and on a bare $null value.
def build_comparison(attribute: str, operator: str, value: Token) -> str:
    if value.kind == WORD and value.text.lower() == "$null":
        return null_form(attribute, operator)
    if operator in MATCHING_RULES:
        return matching_rule_form(attribute, operator, value.text)
    if operator in PATTERN_FORMS:
        return pattern_form(attribute, operator, value.text)
    return simple_form(attribute, operator, value.text)


# Renders an absence test, which only the equality operators can express.
def null_form(attribute: str, operator: str) -> str:
    template = NULL_FORMS.get(operator)
    if template is None:
        raise BackendError(
            f"Operator '{operator}' does not accept a $null value.",
            INVALID_FILTER,
            "InvalidArgument",
            operator,
        )
    return template.format(attribute=attribute)


# Renders a bitwise or chain test through its published matching rule.
def matching_rule_form(attribute: str, operator: str, value: str) -> str:
    rule = MATCHING_RULES[operator]
    return f"({attribute}:{rule}:={escape_value(value)})"


# Renders a wildcard test, keeping '*' and escaping everything else.
def pattern_form(attribute: str, operator: str, value: str) -> str:
    template = PATTERN_FORMS[operator]
    return template.format(attribute=attribute, value=escape_pattern(value))


# Renders a comparison whose value is matched literally.
def simple_form(attribute: str, operator: str, value: str) -> str:
    template = SIMPLE_FORMS[operator]
    return template.format(attribute=attribute, value=escape_value(value))
