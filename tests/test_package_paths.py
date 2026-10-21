"""Tests for the check comparing an installation's paths with MODULE.yaml."""

from __future__ import annotations

from tests.package_paths import covered, declared_paths, undeclared

WRITES = {
    "config_dir": "/etc/hardensamba/samba-powershell/",
    "paths": [
        "/usr/bin/samba-ad-backend",
        "/usr/lib/python3/dist-packages/samba_powershell/",
        "/usr/lib/python3/dist-packages/samba_powershell-*.dist-info/",
        "/usr/share/samba-powershell/",
    ],
}


# Every kind of entry the manifest can carry becomes one path entry.
def test_declared_paths_gathers_every_entry() -> None:
    entries = declared_paths(WRITES)
    assert entries[0] == "/etc/hardensamba/samba-powershell/"
    assert "/usr/bin/samba-ad-backend" in entries


# A directory entry covers what is under it, a file entry only itself, and a
# '*' stands for the version in a dist-info directory name.
def test_entries_cover_what_they_name() -> None:
    assert covered("/usr/share/samba-powershell/Modules/SambaAD/SambaAD.psm1",
                   "/usr/share/samba-powershell/")
    assert covered("/usr/share/samba-powershell", "/usr/share/samba-powershell/")
    assert not covered("/usr/bin/samba-ad-backend.old", "/usr/bin/samba-ad-backend")
    assert covered("/usr/lib/python3/dist-packages/samba_powershell-0.1.0.dist-info/RECORD",
                   "/usr/lib/python3/dist-packages/samba_powershell-*.dist-info/")


# The listing a package gives is clean when every file is declared and the
# directories above them are only shared ground.
def test_a_declared_listing_is_clean() -> None:
    listing = ["/.", "/usr", "/usr/bin", "/usr/bin/samba-ad-backend", "/usr/lib/python3",
               "/usr/lib/python3/dist-packages/samba_powershell/cli.py",
               "/usr/share/samba-powershell/Modules/SambaAD"]
    assert undeclared(listing, declared_paths(WRITES)) == []


# A file written anywhere the manifest does not name is reported, which is the
# undeclared write contract 2.3 forbids.
def test_an_undeclared_write_is_reported() -> None:
    listing = ["/usr/bin/samba-ad-backend", "/etc/cron.d/samba-powershell",
               "/etc/profile.d/samba-powershell.sh"]
    assert undeclared(listing, declared_paths(WRITES)) == [
        "/etc/cron.d/samba-powershell", "/etc/profile.d/samba-powershell.sh"]
