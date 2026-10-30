#!/bin/sh
#
# Publishes the built package into a signed archive and installs it from there,
# through apt alone, in a fresh debian:stable container, so what is proved is what
# a client gets: a signature apt checks, and dependencies apt resolves on its own.
# Nothing but PowerShell's repository is set up first. CI runs it after
# ci_build.sh:
#
#   docker run --rm -v "$PWD:/src" -w /src debian:stable sh tests/package/test_apt_archive.sh
#
# The key is a throwaway, made and destroyed here.

set -eu
export DEBIAN_FRONTEND=noninteractive

fail() {
    echo "test_apt_archive: $*" >&2
    exit 1
}

apt-get update
apt-get install -y --no-install-recommends apt-utils ca-certificates curl gnupg
. /etc/os-release
curl -fsSLo /tmp/packages-microsoft-prod.deb \
    "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb"
dpkg -i /tmp/packages-microsoft-prod.deb

ARCHIVE=$(mktemp -d)
chmod 0755 "$ARCHIVE"
GNUPGHOME=$(mktemp -d)
export GNUPGHOME
chmod 700 "$GNUPGHOME"
gpg --batch --quiet --passphrase '' --quick-generate-key 'throwaway archive key' rsa3072 sign 1d
KEY=$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr:/ { print $10; exit }')
gpg --export "$KEY" > "$ARCHIVE/key.gpg"
chmod 0644 "$ARCHIVE/key.gpg"

mkdir -p "$ARCHIVE/pool/main/s/samba-powershell"
cp dist/samba-powershell_*_all.deb "$ARCHIVE/pool/main/s/samba-powershell/"
sh tools/apt_publish.sh "$ARCHIVE" "$KEY"
chmod -R a+rX "$ARCHIVE"

SOURCE=/etc/apt/sources.list.d/samba-powershell.list
echo "deb [signed-by=$ARCHIVE/key.gpg] file:$ARCHIVE $VERSION_CODENAME main" > "$SOURCE"

# A signature that does not verify must stop apt from reading the archive.
cp "$ARCHIVE/dists/$VERSION_CODENAME/InRelease" /tmp/InRelease.good
sed -i 's/^Origin: HardenSamba/Origin: Tampered/' "$ARCHIVE/dists/$VERSION_CODENAME/InRelease"
if apt-get update 2>&1 | tee /tmp/tampered.log | grep -q 'NO_PUBKEY\|BADSIG\|not signed\|is not valid'; then
    echo "tampered archive refused"
else
    cat /tmp/tampered.log
    fail "apt accepted a tampered InRelease"
fi
cp /tmp/InRelease.good "$ARCHIVE/dists/$VERSION_CODENAME/InRelease"

apt-get update
apt-get install -y --no-install-recommends samba-powershell

for package in samba-powershell python3-ldap libsasl2-modules-gssapi-mit powershell; do
    dpkg -s "$package" >/dev/null 2>&1 || fail "$package is not installed"
done
if dpkg -s samba-adws >/dev/null 2>&1; then
    fail "samba-adws was installed"
fi
python3 -c 'import ldap, ldap.sasl, ldap.controls' || fail "python-ldap does not import"
ls /usr/lib/x86_64-linux-gnu/sasl2/libgssapiv2.* >/dev/null 2>&1 \
    || ls /usr/lib/*/sasl2/libgssapiv2.* >/dev/null 2>&1 \
    || fail "the Kerberos SASL plugin is missing"

pwsh -NoProfile -NonInteractive -File tests/package/check_module.ps1 \
    -ModuleBase /usr/local/share/powershell/Modules/SambaAD \
    -ExpectedErrorId SambaAD.ServerRequired

apt-get purge -y samba-powershell
rm -rf "$ARCHIVE" "$GNUPGHOME" "$SOURCE"
echo "Installation from the signed archive passed."
