"""Stub of python-ldap that composes the real backend without a network."""

from __future__ import annotations

SCOPE_BASE = 0
SCOPE_ONELEVEL = 1
SCOPE_SUBTREE = 2
VERSION3 = 3
OPT_PROTOCOL_VERSION = 1
OPT_REFERRALS = 2
OPT_X_SASL_NOCANON = 3
OPT_X_SASL_SECPROPS = 4
OPT_NETWORK_TIMEOUT = 5
OPT_TIMEOUT = 6

SCHEMA_NC = "CN=Schema,CN=Configuration,DC=example,DC=com"

# What the stub schema answers for: syntax OID and single-valued.
SCHEMA = {"userAccountControl": (b"2.5.5.9", b"TRUE"), "stubServer": (b"2.5.5.12", b"TRUE"),
          "requestedCount": (b"2.5.5.9", b"TRUE"), "memberOf": (b"2.5.5.1", b"FALSE")}


# Mirrors the failure python-ldap raises: one dictionary in the first argument.
class LDAPError(Exception):
    pass


# The failure python-ldap raises when nothing answers.
class SERVER_DOWN(LDAPError):
    pass


# Answers reads and searches from a fixed table instead of a directory.
class StubConnection:
    # Records the server the backend selected.
    def __init__(self, uri: str) -> None:
        self.server = uri.removeprefix("ldap://").rpartition(":")[0]
        self.answers: dict[int, list[tuple[str, dict[str, list[bytes]]]]] = {}

    # Accepts every option.
    def set_option(self, option: int, value: object) -> None:
        return None

    # Accepts the bind: the stub has no ticket to check.
    def sasl_interactive_bind_s(self, who: str, auth: object) -> None:
        return None

    # Returns the RootDSE or one object, or raises the not-found failure, in the
    # shapes a directory answers with: bytes, an objectClass hierarchy, a
    # non-ASCII value, one memberOf, and the server echoed back so composition
    # can see -Server arrive.
    def search_ext_s(self, base: str, scope: int, filterstr: str,
                     attrlist: list[str] | None) -> list[tuple[str, dict[str, list[bytes]]]]:
        if base == "":
            return [("", {"schemaNamingContext": [SCHEMA_NC.encode()],
                         "defaultNamingContext": [b"DC=example,DC=com"]})]
        if "missing" in base.lower():
            raise LDAPError({"result": 32, "desc": "No such object", "info": base})
        return [(base, {
            "name": ["Année".encode()],
            "objectClass": [b"top", b"person", b"organizationalPerson", b"user"],
            "userAccountControl": [b"512"],
            "stubServer": [self.server.encode()],
            "requestedCount": [str(len(attrlist or ())).encode()],
            "memberOf": [b"CN=Staff,DC=example,DC=com"],
        })]

    # Answers schema lookups from the table, and resolves the one account name
    # the composition test uses.
    def search_ext(self, base: str, scope: int, filterstr: str, attrlist: list[str] | None,
                   serverctrls: list[object]) -> int:
        answer: list[tuple[str, dict[str, list[bytes]]]] = []
        if base == SCHEMA_NC:
            answer = [(f"CN={name},{SCHEMA_NC}", {
                "lDAPDisplayName": [name.encode()], "attributeSyntax": [syntax],
                "isSingleValued": [single], "systemFlags": [b"16"]})
                for name, (syntax, single) in SCHEMA.items()
                if f"(lDAPDisplayName={name.lower()})" in filterstr]
        elif "(sAMAccountName=alice)" in filterstr:
            answer = [("CN=Alice,DC=example,DC=com", {})]
        self.answers[len(self.answers) + 1] = answer
        return len(self.answers)

    # Answers one search, complete in one page.
    def result3(self, msgid: int) -> tuple[int, list[tuple[str, dict[str, list[bytes]]]],
                                           int, list[object]]:
        return 101, self.answers[msgid], msgid, []


# Opens a stub connection, as ldap.initialize does.
def initialize(uri: str) -> StubConnection:
    return StubConnection(uri)
