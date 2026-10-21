#!/bin/sh
#
# Installs, exercises and removes samba-powershell the documented ways, as
# root, on a disposable Debian system that has PowerShell, samba-adws (or its
# stand-in) and python3-yaml installed and no samba-powershell:
#
#   sh tests/test_package.sh deb ../samba-powershell_0.1.0-1_all.deb
#   sh tests/test_package.sh coexist ../samba-powershell_0.1.0-1_all.deb
#   sh tests/test_package.sh manual
#
# deb installs the package, coexist installs it over a manual installation,
# manual runs install.sh. Each checks, as root and as the unprivileged user
# nobody, that the cmdlets complete and resolve in a fresh pwsh with no
# Import-Module and that the module is listed where it belongs; that every path
# the installation added, maintainer scripts included, is declared in
# MODULE.yaml; and that removal adds nothing the system did not have before.
# Installations run under umask 077, the strictest a hardened system uses.

set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LINK=/usr/local/share/powershell/Modules/SambaAD
TARGET=/usr/share/samba-powershell/Modules/SambaAD
WORK=$(mktemp -d)
chmod 0755 "$WORK"
trap 'rm -rf "$WORK"' EXIT
unset SAMBA_AD_SERVER || true
export DEBIAN_FRONTEND=noninteractive

fail() {
    echo "test_package: $*" >&2
    exit 1
}

# Every path under the trees an installation may write, less the package
# manager's own state and the logs and caches any command leaves.
snapshot() {
    find /usr /etc /opt /srv /var \( -path /var/lib/dpkg -o -path /var/lib/apt \
        -o -path /var/cache -o -path /var/log -o -path /var/tmp -o -path /var/backups \
        -o -name __pycache__ \) -prune -o -print 2>/dev/null | LC_ALL=C sort
}

# The paths added since the snapshot taken into the named file.
added_since() {
    snapshot | LC_ALL=C comm -13 "$1" -
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

# Runs the module check in a fresh pwsh as root, then as the user nobody, who
# can only read what the installation made readable to everyone.
check_module() {
    pwsh -NoProfile -NonInteractive -File "$ROOT/tests/package/check_module.ps1" \
        -ModuleBase "$1" -ExpectedErrorId "$(expected_error)"
    home=$(mktemp -d "$WORK/nobody.XXXXXX")
    cp "$ROOT/tests/package/check_module.ps1" "$home/"
    chown -R nobody "$home"
    runuser -u nobody -- env HOME="$home" pwsh -NoProfile -NonInteractive \
        -File "$home/check_module.ps1" -ModuleBase "$1" -ExpectedErrorId "$(expected_error)" \
        || fail "the unprivileged user nobody cannot use the module at $1"
}

check_declared() {
    python3 -c 'import yaml' 2>/dev/null || fail "python3-yaml is required"
    python3 "$ROOT/tests/package_paths.py" "$ROOT/MODULE.yaml" \
        || fail "a path above was written but MODULE.yaml does not declare it"
}

assert_restored() {
    left=$(added_since "$1")
    [ -z "$left" ] || fail "removal left behind: $left"
    named=$(find /usr /etc \( -name '*samba-powershell*' -o -name '*samba_powershell*' \
        -o -name 'samba-ad-backend*' -o -name SambaAD \) -print 2>/dev/null)
    [ -z "$named" ] || fail "removal left behind: $named"
}

check_relationships() {
    depends=$(dpkg-deb -f "$1" Depends)
    echo "$depends" | grep -Eq '(^|, )powershell($|,| )' || fail "Depends lacks powershell: $depends"
    echo "$depends" | grep -q 'samba-adws (>= 1.0.0)' \
        || fail "Depends lacks samba-adws (>= 1.0.0): $depends"
}

install_deb() {
    (umask 077 && apt-get install -y --no-install-recommends "$1") >"$WORK/apt.log" 2>&1 \
        || { cat "$WORK/apt.log"; fail "apt-get could not install $1"; }
}

deb_mode() {
    deb=$(readlink -f "$1")
    check_relationships "$deb"
    snapshot >"$WORK/before"
    install_deb "$deb"
    samba-ad-backend status | grep -qx 'samba-ad-backend: ready' \
        || fail "the packaged backend does not start"
    { dpkg -L samba-powershell; added_since "$WORK/before"; } | check_declared
    [ "$(readlink "$LINK")" = "$TARGET" ] || fail "postinst did not link $LINK to $TARGET"
    check_module "$LINK"
    if sh "$ROOT/install.sh" >/dev/null 2>&1; then
        fail "install.sh ran beside the installed package"
    fi
    if sh "$ROOT/install.sh" --uninstall >/dev/null 2>&1; then
        fail "install.sh --uninstall ran beside the installed package"
    fi
    [ "$(readlink "$LINK")" = "$TARGET" ] || fail "install.sh touched the package's link"
    [ ! -e /usr/local/lib/samba-powershell ] || fail "install.sh wrote beside the package"
    apt-get remove -y samba-powershell >"$WORK/apt.log" 2>&1
    if [ -L "$LINK" ] || [ -e "$LINK" ]; then
        fail "apt-get remove left $LINK"
    fi
    apt-get purge -y samba-powershell >"$WORK/apt.log" 2>&1
    assert_restored "$WORK/before"
    echo "test_package: the package installs, works, declares its writes and removes clean"
}

coexist_mode() {
    deb=$(readlink -f "$1")
    snapshot >"$WORK/before"
    (umask 077 && sh "$ROOT/install.sh") >/dev/null
    install_deb "$deb"
    [ -d "$LINK" ] && [ ! -L "$LINK" ] && [ -f "$LINK/SambaAD.psd1" ] \
        || fail "postinst replaced the manual installation at $LINK"
    grep -q 'is not a link and was left as it is' "$WORK/apt.log" \
        || fail "postinst did not report the manual installation it left"
    if sh "$ROOT/install.sh" >/dev/null 2>&1; then
        fail "install.sh ran beside the installed package"
    fi
    sh "$ROOT/install.sh" --uninstall | grep -q 'dpkg-reconfigure' \
        || fail "install.sh --uninstall did not say how to link the packaged module"
    dpkg-reconfigure samba-powershell
    [ "$(readlink "$LINK")" = "$TARGET" ] || fail "dpkg-reconfigure did not link $LINK"
    check_module "$LINK"
    apt-get purge -y samba-powershell >"$WORK/apt.log" 2>&1
    assert_restored "$WORK/before"
    echo "test_package: the package installs over a manual installation and hands over clean"
}

manual_mode() {
    snapshot >"$WORK/before"
    (umask 077 && sh "$ROOT/install.sh")
    (umask 077 && sh "$ROOT/install.sh")
    added_since "$WORK/before" | check_declared
    [ -d "$LINK" ] && [ ! -L "$LINK" ] || fail "install.sh did not install a module directory"
    check_module "$LINK"
    install -m 0644 "$ROOT/install.sh" "$WORK/install.sh"
    if runuser -u nobody -- sh "$WORK/install.sh" --uninstall >"$WORK/nobody.log" 2>&1; then
        fail "install.sh --uninstall ran as an unprivileged user"
    fi
    grep -q 'must run as root' "$WORK/nobody.log" \
        || fail "install.sh --uninstall as nobody failed otherwise: $(cat "$WORK/nobody.log")"
    sh "$ROOT/install.sh" --uninstall
    assert_restored "$WORK/before"
    echo "test_package: install.sh installs, works, declares its writes and uninstalls clean"
}

[ "$(id -u)" -eq 0 ] || fail "run as root on a disposable system"

case "${1:-}" in
    deb|coexist)
        [ -n "${2:-}" ] || fail "usage: sh tests/test_package.sh $1 FILE.deb"
        "${1}_mode" "$2"
        ;;
    manual)
        manual_mode
        ;;
    *)
        fail "usage: sh tests/test_package.sh deb|coexist FILE.deb | manual"
        ;;
esac
