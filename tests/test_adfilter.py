"""Table-driven tests for the -Filter to LDAP translator."""

from __future__ import annotations

import pytest

from samba_powershell.adfilter import translate_filter
from samba_powershell.errors import BackendError

TRANSLATIONS = [
    ("name -eq 'alice'", "(name=alice)"),
    ("name -ne 'alice'", "(!(name=alice))"),
    ("uidNumber -lt 5", "(!(uidNumber>=5))"),
    ("uidNumber -le 5", "(uidNumber<=5)"),
    ("uidNumber -gt 5", "(!(uidNumber<=5))"),
    ("uidNumber -ge 5", "(uidNumber>=5)"),
    ("name -like 'al*'", "(name=al*)"),
    ("name -notlike 'al*'", "(!(name=al*))"),
    ("name -approx 'alice'", "(name~=alice)"),
    (
        "userAccountControl -band 2",
        "(userAccountControl:1.2.840.113556.1.4.803:=2)",
    ),
    (
        "userAccountControl -bor 2",
        "(userAccountControl:1.2.840.113556.1.4.804:=2)",
    ),
    (
        "memberOf -recursivematch 'CN=Team'",
        "(memberOf:1.2.840.113556.1.4.1941:=CN=Team)",
    ),
    ("mail -eq $null", "(!(mail=*))"),
    ("mail -ne $null", "(mail=*)"),
    ("name -eq 'a' -and mail -eq 'b'", "(&(name=a)(mail=b))"),
    ("name -eq 'a' -or mail -eq 'b'", "(|(name=a)(mail=b))"),
    ("-not name -eq 'a'", "(!(name=a))"),
    ("name -eq 'a' -and -not mail -eq 'b'", "(&(name=a)(!(mail=b)))"),
]

# -not binds tightest, then -and, then -or; parentheses override that.
PRECEDENCE = [
    (
        "a -eq 1 -or b -eq 2 -and c -eq 3",
        "(|(a=1)(&(b=2)(c=3)))",
    ),
    (
        "(a -eq 1 -or b -eq 2) -and c -eq 3",
        "(&(|(a=1)(b=2))(c=3))",
    ),
    (
        "a -eq 1 -and b -eq 2 -and c -eq 3",
        "(&(a=1)(b=2)(c=3))",
    ),
]

REJECTIONS = [
    ("name -foo 'a'", "-foo"),
    ("name -eq", "a value"),
    ("(name -eq 'a'", "never closed"),
    ("name -eq 'a", "never closed"),
    ("name -lt $null", "$null"),
    ("name -eq 'a' extra", "extra"),
    ("1name -eq 'a'", "1name"),
    ("name -eq -and", "-and"),
    ("", "empty"),
]


# Every supported operator renders its documented LDAP form.
@pytest.mark.parametrize(("expression", "expected"), TRANSLATIONS)
def test_operator_renders_its_ldap_form(expression: str, expected: str) -> None:
    assert translate_filter(expression) == expected


# Operator precedence and grouping survive the translation.
@pytest.mark.parametrize(("expression", "expected"), PRECEDENCE)
def test_precedence_is_preserved(expression: str, expected: str) -> None:
    assert translate_filter(expression) == expected


# An unsupported construct is named, and never yields a filter.
@pytest.mark.parametrize(("expression", "fragment"), REJECTIONS)
def test_unsupported_construct_is_rejected(expression: str, fragment: str) -> None:
    with pytest.raises(BackendError) as raised:
        translate_filter(expression)
    assert raised.value.error_id == "SambaAD.InvalidFilter"
    assert fragment in raised.value.message


# A value carrying filter metacharacters is matched literally, not as syntax.
def test_metacharacters_in_a_value_are_escaped() -> None:
    assert translate_filter("name -eq 'a*b)c('") == "(name=a\\2ab\\29c\\28)"


# The -like wildcard survives while its neighbours are still escaped.
def test_like_keeps_the_wildcard_but_escapes_the_rest() -> None:
    assert translate_filter("name -like 'a*b)c'") == "(name=a*b\\29c)"


# A quoted $null is a literal value, unlike the bare token.
def test_quoted_null_is_a_literal_value() -> None:
    assert translate_filter("name -eq '$null'") == "(name=$null)"
