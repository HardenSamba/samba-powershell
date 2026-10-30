"""Offline stand-in for the python-ldap modules, used by the adapter tests."""

from __future__ import annotations

from types import SimpleNamespace

from samba_powershell.ldap_api import LdapApi

SCHEMA_NC = "CN=Schema,CN=Configuration,DC=example,DC=com"
ALICE_DN = "CN=Alice,CN=Users,DC=example,DC=com"
# A SID whose bytes are valid UTF-8, which only the schema can tell from text.
BUILTIN_SID = b"\x01\x02\x00\x00\x00\x00\x00\x05 \x00\x00\x00 \x02\x00\x00"
ALICE = {
    "objectSid": [BUILTIN_SID],
    "objectClass": [b"top", b"user"],
    "name": ["Année".encode()],
    "description": [b"\xff\xfe not text"],
}


# The failure python-ldap raises when nothing answers.
class ServerDown(Exception):
    pass


# The paged results control, reduced to what the adapter reads and sends.
class PagedControl:
    controlType = "1.2.840.113556.1.4.319"

    # Stores what one page asks for.
    def __init__(self, criticality: bool, size: int, cookie: bytes) -> None:
        self.criticality = criticality
        self.size = size
        self.cookie = cookie


# A request control, reduced to what the adapter sends.
class RequestControl:
    # Stores the control as it would go on the wire.
    def __init__(self, control_type: str, criticality: bool, value: bytes) -> None:
        self.controlType = control_type
        self.criticality = criticality
        self.value = value


# A connection answering from fixed tables, recording every call it was given.
class FakeConnection:
    # Starts with no pages queued, the bind succeeding and the session encrypted.
    def __init__(self, uri: str, bind_failure: Exception | None = None,
                 strength: object = 256) -> None:
        self.uri = uri
        self.bind_failure = bind_failure
        self.strength = strength
        self.controls: list[list[RequestControl] | None] = []
        self.options: dict[int, object] = {}
        self.pages: list[list[tuple[str | None, dict[str, list[bytes]]]]] = []
        self.searches: list[tuple[str, int, str, list[str] | None, int]] = []
        self.reads: list[tuple[str, list[str] | None]] = []
        self.pending: dict[int, PagedControl] = {}

    # Records one session option.
    def set_option(self, option: int, value: object) -> None:
        self.options[option] = value

    # Reads the session's strength; a session with no layer has none to read.
    def get_option(self, option: int) -> object:
        if self.strength is None:
            raise ValueError("option error")
        return self.strength

    # Succeeds, or fails the way the test asked.
    def sasl_interactive_bind_s(self, who: str, auth: object) -> None:
        if self.bind_failure is not None:
            raise self.bind_failure

    # Answers the RootDSE and one known object; anything else is hidden.
    def search_ext_s(self, base: str, scope: int, filterstr: str, attrlist: list[str] | None,
                     serverctrls: list[RequestControl] | None = None,
                     ) -> list[tuple[str | None, dict[str, list[bytes]]]]:
        self.reads.append((base, attrlist))
        self.controls.append(serverctrls)
        if base == "":
            return [("", {"schemaNamingContext": [SCHEMA_NC.encode()]})]
        return [(ALICE_DN, ALICE)] if base == ALICE_DN else [(None, {})]

    # Starts one paged search, recording the size and control it carried.
    def search_ext(self, base: str, scope: int, filterstr: str, attrlist: list[str] | None,
                   serverctrls: list[PagedControl]) -> int:
        self.searches.append((base, scope, filterstr, attrlist, serverctrls[0].size))
        self.pending[len(self.searches)] = serverctrls[0]
        return len(self.searches)

    # Answers the schema with its one binary attribute, and anything else from
    # the queued pages, with a cookie while more pages remain.
    def result3(self, msgid: int) -> tuple[int, list[tuple[str | None, dict[str, list[bytes]]]],
                                           int, list[object]]:
        if self.searches[msgid - 1][0] == SCHEMA_NC:
            page: list[tuple[str | None, dict[str, list[bytes]]]] = [
                ("CN=x", {"lDAPDisplayName": [b"objectSid"]})]
            return 101, page, msgid, []
        page = self.pages.pop(0)
        cookie = b"more" if self.pages else b""
        return 101, page, msgid, [PagedControl(False, 0, cookie)]


# The three modules, with the names the adapter reads from them. initialize
# hands back the connection given, so a test can read what was done to it.
def fake_api(connection: FakeConnection) -> LdapApi:
    return LdapApi(
        SimpleNamespace(
            initialize=lambda uri: setattr(connection, "uri", uri) or connection,
            SERVER_DOWN=ServerDown, VERSION3=3, SCOPE_BASE=0, SCOPE_ONELEVEL=1, SCOPE_SUBTREE=2,
            OPT_PROTOCOL_VERSION=1, OPT_REFERRALS=2, OPT_X_SASL_NOCANON=3,
            OPT_X_SASL_SECPROPS=4, OPT_NETWORK_TIMEOUT=5, OPT_TIMEOUT=6, OPT_X_SASL_SSF=7),
        SimpleNamespace(gssapi=lambda authz: ("gssapi", authz)),
        SimpleNamespace(SimplePagedResultsControl=PagedControl, RequestControl=RequestControl))
