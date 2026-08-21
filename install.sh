#!/bin/sh
#
# Manual installation of samba-powershell on a Debian or Ubuntu system without
# the package archive. It installs the same files the package does:
#
#   /usr/lib/python3/dist-packages/samba_powershell/   the backend
#   /usr/local/bin/samba-ad-backend                    the backend entry point
#   /usr/share/samba-powershell/SambaAD/               the PowerShell module
#   /etc/profile.d/samba-powershell.sh                 the module search path
#
# The Debian package is the reference method; this exists for a system that
# cannot reach the archive. It is idempotent.

set -eu

MODULE="samba-powershell"
SOURCE="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_DIR="/usr/lib/python3/dist-packages/samba_powershell"
MODULE_DIR="/usr/share/samba-powershell/SambaAD"

if [ "$(id -u)" -ne 0 ]; then
    echo "${MODULE}: this installer must run as root" >&2
    exit 1
fi

echo "${MODULE}: installing the backend"
rm -rf "${PACKAGE_DIR}"
install -d -m 0755 "${PACKAGE_DIR}"
cp -a "${SOURCE}/src/samba_powershell/." "${PACKAGE_DIR}/"

install -d -m 0755 /usr/local/bin
cat >/usr/local/bin/samba-ad-backend <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 -m samba_powershell.cli "$@"
LAUNCHER
chmod 0755 /usr/local/bin/samba-ad-backend

echo "${MODULE}: installing the PowerShell module"
rm -rf "${MODULE_DIR}"
install -d -m 0755 "${MODULE_DIR}"
cp -a "${SOURCE}/powershell/SambaAD/." "${MODULE_DIR}/"

install -m 0644 "${SOURCE}/debian/psmodulepath.sh" /etc/profile.d/samba-powershell.sh

cat <<NEXT

${MODULE} is installed. PowerShell finds the module on the next login shell, or
in this one with:

    export PSModulePath="/usr/share/samba-powershell:\${PSModulePath}"

Then, with pwsh installed and a Kerberos ticket for the domain:

    kinit administrator@YOUR.REALM
    pwsh -c 'Import-Module SambaAD; Get-ADUser -Identity "CN=...,DC=...,DC=..." -Server dc1.your.realm'

pwsh is not in Debian stable; see docs/packaging.md.
NEXT
