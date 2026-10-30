"""Tests for the adapter between the backend and python-ldap."""

from __future__ import annotations

import socket

import pytest

from samba_powershell.client_error import translate_client_error
from samba_powershell.ldap_directory import LdapDirectory
from samba_powershell.ldap_session import open_directory
from tests.fake_ldap import ALICE_DN, BUILTIN_SID, SCHEMA_NC, FakeConnection, ServerDown, fake_api

BASE = "DC=example,DC=com"
ENTRY = ("CN=A," + BASE, {"cn": [b"A"]})


# A directory over a fresh fake connection.
def directory() -> tuple[LdapDirectory, FakeConnection]:
    connection = FakeConnection("")
    return LdapDirectory(connection, fake_api(connection)), connection


# Values come back in the shapes the renderer reads: a binary SID stays bytes
# though it is valid UTF-8, text decodes, several values make a tuple, and text
# that is not UTF-8 stays bytes rather than failing the read.
def test_values_take_the_shapes_the_renderer_reads() -> None:
    read = directory()[0].get_by_dn(ALICE_DN)
    assert read["objectSid"] == BUILTIN_SID
    assert read["name"] == "Année"
    assert read["objectClass"] == ("top", "user")
    assert read["description"] == b"\xff\xfe not text"


# The distinguished name is present whether or not the read named it.
def test_the_distinguished_name_is_always_present() -> None:
    assert directory()[0].get_by_dn(ALICE_DN, ["name"])["distinguishedName"] == ALICE_DN


# An empty projection asks for the whole object, and a named one for those names.
def test_the_projection_reaches_the_server() -> None:
    reader, connection = directory()
    reader.get_by_dn(ALICE_DN)
    reader.get_by_dn(ALICE_DN, ["mail"])
    assert [read for read in connection.reads if read[0] == ALICE_DN] == [
        (ALICE_DN, None), (ALICE_DN, ["mail"])]


# An object the caller may not see answers with nothing, which is not an object.
def test_an_empty_answer_is_a_missing_object() -> None:
    with pytest.raises(LookupError):
        directory()[0].get_by_dn("CN=Hidden," + BASE)


# The RootDSE and the schema are each asked once per session.
def test_the_schema_and_the_root_are_asked_once() -> None:
    reader, connection = directory()
    reader.get_by_dn(ALICE_DN)
    reader.get_by_dn(ALICE_DN)
    assert reader.naming_context("schemaNamingContext") == SCHEMA_NC
    assert [read[0] for read in connection.reads].count("") == 1
    assert [search[0] for search in connection.searches] == [SCHEMA_NC]


# A RootDSE without the context is a failure, not an empty base to search.
def test_an_unpublished_naming_context_is_refused() -> None:
    with pytest.raises(ValueError, match="configurationNamingContext"):
        directory()[0].naming_context("configurationNamingContext")


# Pages are followed until the limit, which also bounds what the last one asks
# for; search references do not count as entries.
def test_a_search_follows_pages_up_to_its_limit() -> None:
    reader, connection = directory()
    connection.pages = [[ENTRY, (None, {})], [ENTRY, ENTRY], [ENTRY]]
    found = reader.search(BASE, "Subtree", "(cn=A)", ["cn"], 3)
    assert [item["cn"] for item in found] == ["A", "A", "A"]
    assert [search[4] for search in connection.searches if search[0] == BASE] == [3, 2]


# A search with fewer matches than its limit stops when the server says so.
def test_a_search_stops_when_the_server_is_done() -> None:
    reader, connection = directory()
    connection.pages = [[ENTRY]]
    assert len(reader.search(BASE, "OneLevel", "(cn=A)", ["cn"], 10)) == 1
    assert connection.searches[0][1] == 1


# The session binds through GSSAPI on the host and port asked for, with
# encryption required, referrals off and the name kept as the caller gave it.
def test_the_session_requires_protection() -> None:
    connection = FakeConnection("")
    open_directory(fake_api(connection), "dc1.example.com", 1389, 30.0)
    assert connection.uri == "ldap://dc1.example.com:1389"
    assert connection.options == {1: 3, 2: 0, 3: 1, 4: "minssf=56", 5: 10.0, 6: 30.0}


# What the library calls "Can't contact LDAP server" is replaced by the reason
# the operating system gives, which is the one an operator can act on.
def test_an_unreachable_server_reports_the_system_reason(
        monkeypatch: pytest.MonkeyPatch) -> None:

    # Fails the way a closed port does.
    def refused(address: tuple[str, int], timeout: float) -> socket.socket:
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr(socket, "create_connection", refused)
    connection = FakeConnection("", ServerDown({"result": -1, "desc": "x"}))
    with pytest.raises(ConnectionRefusedError) as raised:
        open_directory(fake_api(connection), "dc1", 389, 30.0)
    assert "check the port" in translate_client_error(raised.value, "dc1", "x").message


# A port that answers the second time keeps the library's own failure.
def test_a_port_that_answers_keeps_the_library_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        connection = FakeConnection("", ServerDown({"result": -1, "desc": "x"}))
        with pytest.raises(ServerDown):
            open_directory(fake_api(connection), "127.0.0.1", port, 30.0)
