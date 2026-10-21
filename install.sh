#!/bin/sh
#
# Manual installation of samba-powershell on Debian 12 or later, or Ubuntu
# 24.04 or later, for a system that cannot reach the package archive, and its
# removal with --uninstall.
#
# The Debian package is the reference method. This installs the same two
# halves, the Python backend and the SambaAD PowerShell module, under
# /usr/local, which Debian keeps for what the administrator installs by hand,
# so it never writes a file dpkg owns:
#
#   /usr/local/lib/samba-powershell/samba_powershell/   the backend
#   /usr/local/bin/samba-ad-backend                     its launcher
#   /usr/local/share/powershell/Modules/SambaAD/        the PowerShell module
#
# It refuses to run while the package is installed, since both would answer to
# the same command. It checks its own result before it reports success. It is
# idempotent: running it again replaces the files with the checkout's.
#
# Usage: sh install.sh [--uninstall]

set -eu
umask 022

NAME=samba-powershell
SOURCE=$(cd "$(dirname "$0")" && pwd)
LIB=/usr/local/lib/samba-powershell
LAUNCHER=/usr/local/bin/samba-ad-backend
MODULES=/usr/local/share/powershell/Modules
MODULE=$MODULES/SambaAD
PACKAGE_MODULE=/usr/share/samba-powershell/Modules/SambaAD
MODULE_FILES="SambaAD.psd1 SambaAD.psm1 SambaAD.Format.ps1xml"
# The interpreter the Debian packages of samba-adws and samba install for;
# another python3 earlier on PATH would not find their modules.
PYTHON=/usr/bin/python3

fail() {
    echo "$NAME: $*" >&2
    exit 1
}

warn() {
    echo "$NAME: warning: $*" >&2
}

package_installed() {
    status=$(dpkg-query -W -f='${db:Status-Status}' "$NAME" 2>/dev/null || true)
    [ "$status" = installed ]
}

refuse_link() {
    if [ "$(readlink "$MODULE")" = "$PACKAGE_MODULE" ]; then
        fail "$MODULE is the package's link; $1"
    fi
    fail "$MODULE is a link of your own; remove it first"
}

uninstall() {
    if [ -L "$MODULE" ]; then
        refuse_link "remove the package with apt instead"
    fi
    rm -rf "$LIB" "$MODULE"
    rm -f "$LAUNCHER"
    rmdir --ignore-fail-on-non-empty "$MODULES" /usr/local/share/powershell 2>/dev/null || true
    echo "$NAME: removed the manual installation"
    if package_installed; then
        echo "$NAME: run 'dpkg-reconfigure $NAME' to link the packaged module"
    fi
}

install_backend() {
    install -d -m 0755 "$LIB" /usr/local/bin
    staging="$LIB/samba_powershell.new"
    rm -rf "$staging"
    cp -R "$SOURCE/src/samba_powershell" "$staging"
    find "$staging" -name __pycache__ -type d -prune -exec rm -rf {} +
    find "$staging" -type d -exec chmod 0755 {} +
    find "$staging" -type f -exec chmod 0644 {} +
    rm -rf "$LIB/samba_powershell"
    mv "$staging" "$LIB/samba_powershell"
    launcher=$(mktemp)
    cat >"$launcher" <<LAUNCHER
#!$PYTHON
import sys
sys.path.insert(0, "$LIB")
from samba_powershell.cli import main
sys.exit(main())
LAUNCHER
    install -m 0755 "$launcher" "$LAUNCHER"
    rm -f "$launcher"
}

install_module() {
    rm -rf "$MODULE"
    install -d -m 0755 "$MODULE"
    for file in $MODULE_FILES; do
        install -m 0644 "$SOURCE/powershell/SambaAD/$file" "$MODULE/$file"
    done
}

verify() {
    "$LAUNCHER" status | grep -qx 'samba-ad-backend: ready' \
        || fail "the backend launcher $LAUNCHER does not start"
    if command -v pwsh >/dev/null 2>&1; then
        pwsh -NoProfile -NonInteractive -Command \
            "if (-not (Get-Module -ListAvailable SambaAD | Where-Object ModuleBase -eq '$MODULE')) { exit 1 }" \
            || fail "pwsh does not find the SambaAD module in $MODULE"
    else
        warn "pwsh is not installed; the module needs PowerShell 7.4 or later, see docs/packaging.md"
    fi
    if ! "$PYTHON" -c 'import samba_adws.search_client' >/dev/null 2>&1; then
        warn "the samba-adws client is not installed; the cmdlets need samba-adws 1.0.0 or later"
    fi
}

[ "$(id -u)" -eq 0 ] || fail "this installer must run as root"

case "${1:-}" in
    --uninstall)
        uninstall
        exit 0
        ;;
    "")
        ;;
    *)
        fail "unknown argument '$1'; usage: sh install.sh [--uninstall]"
        ;;
esac

if package_installed; then
    fail "the $NAME package is installed; remove it with apt before a manual installation"
fi
if [ -L "$MODULE" ]; then
    refuse_link "purge the package first"
fi
[ -x "$PYTHON" ] || fail "python3 is required ($PYTHON, package python3)"
"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
    || fail "Python 3.11 or later is required"
[ -d "$SOURCE/src/samba_powershell" ] && [ -f "$SOURCE/powershell/SambaAD/SambaAD.psd1" ] \
    || fail "run install.sh from a samba-powershell checkout"

install_backend
install_module
verify
echo "$NAME: installed; open a new pwsh and run Get-ADUser -Server <dc>"
