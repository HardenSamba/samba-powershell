"""Bounded searches over the simple paged results control, RFC 2696."""

from __future__ import annotations

from samba_powershell.ldap_api import LdapApi
from samba_powershell.ldap_protocol import LdapConnection, RawEntry

# What one page asks for: Windows refuses to return more than this at a time
# without paging, and any directory may set its own ceiling.
PAGE_SIZE = 1000


# Collects at most limit entries, page by page, and stops asking as soon as it
# has them, so a question about uniqueness never pulls a whole directory. Search
# references are not entries and do not count.
def paged_entries(connection: LdapConnection, api: LdapApi, base: str, scope: int,
                  ldap_filter: str, attributes: list[str] | None, limit: int) -> list[RawEntry]:
    found: list[RawEntry] = []
    cookie = b""
    while len(found) < limit:
        control = api.controls.SimplePagedResultsControl(
            True, size=min(limit - len(found), PAGE_SIZE), cookie=cookie)
        message = connection.search_ext(base, scope, ldap_filter, attributes,
                                        serverctrls=[control])
        _, page, _, answers = connection.result3(message)
        found.extend(entry for entry in page if entry[0] is not None)
        cookie = next_cookie(answers, control.controlType)
        if not cookie:
            break
    return found[:limit]


# The cookie the server answered with, empty when the search is complete or the
# server ignored the control and answered everything at once.
def next_cookie(answers: list[object], control_type: str) -> bytes:
    for answer in answers:
        if getattr(answer, "controlType", None) == control_type:
            cookie: bytes = getattr(answer, "cookie", b"")
            return cookie
    return b""
