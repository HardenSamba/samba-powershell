#!/bin/sh
#
# Provisions a real Samba domain in a disposable container, with no samba-adws
# anywhere, installs the built package, and runs the live acceptance against it.
# This is what proves the module needs nothing on a controller but Samba. CI runs
# it after ci_build.sh, privileged because Samba needs extended attributes:
#
#   docker run --rm --privileged --hostname dc1 -v "$PWD:/src" -w /src \
#       debian:stable sh tests/package/ci_live.sh
#
# The domain and its password exist only inside this container.

set -eu
export DEBIAN_FRONTEND=noninteractive

REALM=CI.TEST
HOST=dc1.ci.test

fail() {
    echo "ci_live: $*" >&2
    exit 1
}

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl openssl
. /etc/os-release
curl -fsSLo /tmp/packages-microsoft-prod.deb \
    "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb"
dpkg -i /tmp/packages-microsoft-prod.deb
apt-get update
apt-get install -y --no-install-recommends samba samba-ad-dc samba-ad-provision samba-dsdb-modules \
    samba-vfs-modules krb5-user ./dist/samba-powershell_*_all.deb
if dpkg -s samba-adws >/dev/null 2>&1; then
    fail "samba-adws is installed"
fi

ADDRESS=$(hostname -i | cut -d' ' -f1)
echo "$ADDRESS $HOST dc1" >> /etc/hosts
cat > /etc/krb5.conf <<CONF
[libdefaults]
    default_realm = $REALM
    dns_lookup_kdc = false
    dns_lookup_realm = false
    rdns = false
[realms]
    $REALM = {
        kdc = $HOST
    }
CONF

PASSWORD="Aa1-$(openssl rand -hex 16)"
rm -f /etc/samba/smb.conf
samba-tool domain provision --realm="$REALM" --domain=CI --server-role=dc \
    --dns-backend=SAMBA_INTERNAL --adminpass="$PASSWORD" --host-name=dc1 --host-ip="$ADDRESS"
samba --foreground --no-process-group &
SAMBA=$!
trap 'kill "$SAMBA" 2>/dev/null || true' EXIT

tries=0
until (exec 3<>"/dev/tcp/$ADDRESS/389") 2>/dev/null \
        || bash -c "exec 3<>/dev/tcp/$ADDRESS/389" 2>/dev/null; do
    tries=$((tries + 1))
    [ "$tries" -lt 60 ] || fail "Samba did not start listening on 389"
    sleep 1
done
if bash -c "exec 3<>/dev/tcp/$ADDRESS/9389" 2>/dev/null; then
    fail "something listens on the ADWS port"
fi

printf '%s\n' "$PASSWORD" | kinit "Administrator@$REALM"
pwsh -NoProfile -NonInteractive -File tests/test_live.ps1 -Server "$HOST" \
    -SamAccountName Administrator -ComputerName DC1 -IpAddress "$ADDRESS"
pwsh -NoProfile -NonInteractive -File tests/test_gallery.ps1 -Server "$HOST" \
    -SamAccountName Administrator
kdestroy -q
