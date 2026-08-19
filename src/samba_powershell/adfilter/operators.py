"""The -Filter operator set and the LDAP form each one produces."""

from __future__ import annotations

# LDAP offers no strict comparison, so -lt and -gt negate the inclusive form.
SIMPLE_FORMS = {
    "-eq": "({attribute}={value})",
    "-ne": "(!({attribute}={value}))",
    "-le": "({attribute}<={value})",
    "-ge": "({attribute}>={value})",
    "-lt": "(!({attribute}>={value}))",
    "-gt": "(!({attribute}<={value}))",
    "-approx": "({attribute}~={value})",
}

# These keep '*' as a wildcard instead of escaping it.
PATTERN_FORMS = {
    "-like": "({attribute}={value})",
    "-notlike": "(!({attribute}={value}))",
}

# Extensible matching rules, identified as published in MS-ADTS.
MATCHING_RULES = {
    "-band": "1.2.840.113556.1.4.803",
    "-bor": "1.2.840.113556.1.4.804",
    "-recursivematch": "1.2.840.113556.1.4.1941",
}

# An absent attribute is tested for presence rather than for a value.
NULL_FORMS = {
    "-eq": "(!({attribute}=*))",
    "-ne": "({attribute}=*)",
}

LOGICAL_NAMES = frozenset({"-and", "-or", "-not"})
COMPARISON_NAMES = (
    frozenset(SIMPLE_FORMS) | frozenset(PATTERN_FORMS) | frozenset(MATCHING_RULES)
)
OPERATOR_NAMES = COMPARISON_NAMES | LOGICAL_NAMES
