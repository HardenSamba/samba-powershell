"""Smoke tests for the package and backend entry point."""

from __future__ import annotations

import pytest
from io import StringIO

from samba_powershell import __version__, cli


# The package exposes a version.
def test_version_is_declared() -> None:
    assert __version__


# The entry point reports its version and exits cleanly.
def test_version_flag_exits_zero() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0


# The status subcommand runs.
def test_status_runs() -> None:
    assert cli.main(["status"]) == 0


# A malformed request becomes JSON instead of a Python traceback.
def test_request_error_is_structured() -> None:
    output = StringIO()
    assert cli.request(StringIO("not-json"), output) == 1
    assert '"error_id":"SambaAD.InvalidRequest"' in output.getvalue()


# A client value that JSON cannot represent stays behind the error boundary.
def test_response_serialisation_error_is_structured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "dispatch", lambda _request: b"not-json-safe")
    source = StringIO('{"version":1,"operation":"test","parameters":{}}')
    output = StringIO()
    assert cli.request(source, output) == 1
    assert '"error_id":"SambaAD.BackendFailure"' in output.getvalue()
