"""Smoke tests: the package imports and the entry point answers."""

from __future__ import annotations

import pytest

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
