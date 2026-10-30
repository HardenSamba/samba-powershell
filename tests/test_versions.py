"""The version is written in five places, and the release refuses any difference."""

from __future__ import annotations

import re
from pathlib import Path

from samba_powershell import __version__

ROOT = Path(__file__).resolve().parent.parent


# Reads one version out of one file; a pattern that stops matching fails the test.
def version_in(path: str, pattern: str) -> str:
    found = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.MULTILINE)
    assert found is not None, path
    return found.group(1)


# A release built from a tree that disagrees would publish a package whose module
# reports another version, so CI catches it long before a tag does.
def test_every_version_agrees() -> None:
    assert {
        version_in("debian/changelog", r"\A\S+ \((.+)-[^-]+\)"),
        version_in("powershell/SambaAD/SambaAD.psd1", r"ModuleVersion = '(.+)'"),
        version_in("pyproject.toml", r'^version = "(.+)"'),
        version_in("MODULE.yaml", r"^version: (.+?)\s*$"),
    } == {__version__}
