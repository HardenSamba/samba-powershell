#!/bin/sh
#
# Installs, exercises and removes samba-powershell the two documented ways, as
# root, on a disposable Debian system with PowerShell and samba-adws (or its
# stand-in) installed:
#
#   sh tests/test_package.sh deb ../samba-powershell_0.1.0-1_all.deb
#   sh tests/test_package.sh manual
#
# Each mode checks that the cmdlets resolve in a fresh pwsh with no
# Import-Module, that the module is listed where the installation put it, that
# every path written is declared in MODULE.yaml, and that removal leaves nothing
# of the module under /usr or /etc. Run it on a system without the module.

set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LINK=/usr/local/share/powershell/Modules/SambaAD
TARGET=/usr/share/samba-powershell/Modules/SambaAD
POWERSHELL_DIR=/usr/local/share/powershell
unset SAMBA_AD_SERVER || true

fail() {
    echo "test_package: $*" >&2
    exit 1
}

# The id the backend's first refusal carries: with the samba-adws client
# present it asks for a server, with the stand-in it reports the client missing.
expected_error() {
    if python3 -c 'import samba_adws.search_client' >/dev/null 2>&1; then
        echo SambaAD.ServerRequired
    else
        echo SambaAD.ClientUnavailable
    fi
}

check_module() {
    pwsh -NoProfile -NonInteractive -File "$ROOT/tests/package/check_module.ps1" \
        -ModuleBase "$1" -ExpectedErrorId "$(expected_error)"
}

check_declared() {
    python3 "$ROOT/tests/package_paths.py" "$ROOT/MODULE.yaml" \
        || fail "a path above was written but MODULE.yaml does not declare it"
}

leftovers() {
    find /usr /etc \( -name '*samba-powershell*' -o -name '*samba_powershell*' \
        -o -name 'samba-ad-backend*' -o -name SambaAD \) -print 2>/dev/null
    if [ "$POWERSHELL_BEFORE" = no ] && [ -e "$POWERSHELL_DIR" ]; then
        echo "$POWERSHELL_DIR"
    fi
}

assert_clean() {
    found=$(leftovers)
    [ -z "$found" ] || fail "left behind under /usr or /etc: $found"
}

deb_mode() {
    deb=$(readlink -f "$1")
    assert_clean
    apt-get install -y --no-install-recommends "$deb"
    samba-ad-backend status | grep -qx 'samba-ad-backend: ready' \
        || fail "the packaged backend does not start"
    { dpkg -L samba-powershell; echo "$LINK"; } | check_declared
    [ "$(readlink "$LINK")" = "$TARGET" ] || fail "postinst did not link $LINK to $TARGET"
    check_module "$LINK"
    if sh "$ROOT/install.sh" >/dev/null 2>&1; then
        fail "install.sh ran beside the installed package"
    fi
    [ ! -e /usr/local/lib/samba-powershell ] || fail "install.sh wrote beside the package"
    apt-get purge -y samba-powershell
    assert_clean
    echo "test_package: the package installs, works, declares its paths and purges clean"
}

manual_mode() {
    assert_clean
    marker=$(mktemp)
    sleep 1
    sh "$ROOT/install.sh"
    sh "$ROOT/install.sh"
    find /usr /etc -newer "$marker" \( -type f -o -type l \) -not -path '*/__pycache__/*' \
        -print | check_declared
    rm -f "$marker"
    [ -d "$LINK" ] && [ ! -L "$LINK" ] || fail "install.sh did not install a module directory"
    check_module "$LINK"
    sh "$ROOT/install.sh" --uninstall
    assert_clean
    echo "test_package: install.sh installs, works, declares its paths and uninstalls clean"
}

[ "$(id -u)" -eq 0 ] || fail "run as root on a disposable system"
if [ -e "$POWERSHELL_DIR" ]; then POWERSHELL_BEFORE=yes; else POWERSHELL_BEFORE=no; fi

case "${1:-}" in
    deb)
        [ -n "${2:-}" ] || fail "usage: sh tests/test_package.sh deb FILE.deb"
        deb_mode "$2"
        ;;
    manual)
        manual_mode
        ;;
    *)
        fail "usage: sh tests/test_package.sh deb FILE.deb | manual"
        ;;
esac
