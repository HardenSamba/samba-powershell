"""Checks that every path an installation wrote is one MODULE.yaml declares.

Usage: python3 tests/package_paths.py MODULE.yaml < paths
Reads one absolute path per line, prints each the manifest does not cover and
exits 1 if there is one. A declared entry ending in '/' covers a directory and
everything under it; any other entry covers that one path; '*' matches within
an entry. A directory that only leads to a declared entry, such as /usr/bin,
is shared ground and allowed.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from fnmatch import fnmatchcase


# The declared write surface, as plain path entries.
def declared_paths(writes: Mapping[str, object]) -> list[str]:
    entries = [value for key, value in writes.items()
               if key in ("config_dir", "smb_conf_fragment") and isinstance(value, str)]
    paths = writes.get("paths", [])
    if isinstance(paths, list):
        entries.extend(path for path in paths if isinstance(path, str))
    return entries


# Whether one entry covers a path: the path itself, or anything under a directory.
def covered(path: str, entry: str) -> bool:
    stem = entry.rstrip("/")
    if fnmatchcase(path, stem):
        return True
    return entry.endswith("/") and fnmatchcase(path, stem + "/*")


# The paths the declared entries neither cover nor lead to.
def undeclared(paths: Iterable[str], entries: list[str]) -> list[str]:
    found: list[str] = []
    for path in (line.strip().rstrip("/") for line in paths):
        leads = any(entry.startswith(path + "/") for entry in entries)
        if path and path != "/." and not leads and not any(covered(path, e) for e in entries):
            found.append(path)
    return found


# Loads the manifest, reads paths from standard input and reports what is undeclared.
def main(argv: list[str]) -> int:
    import yaml

    with open(argv[1], encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    writes = manifest.get("writes", {}) if isinstance(manifest, dict) else {}
    missing = undeclared(sys.stdin, declared_paths(writes))
    for path in missing:
        print(f"undeclared: {path}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
