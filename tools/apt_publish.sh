#!/bin/sh
#
# Regenerates the indexes of the APT archive from its pool, and signs them:
#
#   sh tools/apt_publish.sh <archive-root> [key-id]
#
# The pool, pool/main/s/samba-powershell/*.deb, is the whole state. The layout is
# the one hardensamba-apt decided (docs/packaging.md), so this archive can move
# there unchanged once that one has an origin. The package is Architecture: all
# and one build runs on every release listed, so every suite indexes one pool.
# Without a key the indexes are left unsigned, which apt refuses to use.

set -eu

ROOT=${1:?usage: apt_publish.sh <archive-root> [key-id]}
KEY=${2:-}

SUITES='bookworm trixie'
COMPONENT=main
# 'all' first, and it is not decoration: apt only reads binary-all when Release
# lists it, and a client still asks for its own architecture's index, so those
# must exist even though they stay empty.
EMPTY_ARCHITECTURES='amd64 arm64'

cd "$ROOT"
[ -d "pool/$COMPONENT" ] || {
    echo "apt_publish: $ROOT/pool/$COMPONENT does not exist" >&2
    exit 2
}

# Writes one index and its compressed copy; -n keeps the compressed bytes stable.
write_index() {
    mkdir -p "$(dirname "$1")"
    cat > "$1"
    gzip -9nkf "$1"
}

for suite in $SUITES; do
    rm -rf "dists/$suite"
    apt-ftparchive packages "pool/$COMPONENT" | write_index "dists/$suite/$COMPONENT/binary-all/Packages"
    for architecture in $EMPTY_ARCHITECTURES; do
        write_index "dists/$suite/$COMPONENT/binary-$architecture/Packages" < /dev/null
    done
    # Written outside the directory it scans, or it would checksum itself.
    apt-ftparchive \
        -o APT::FTPArchive::Release::Origin=HardenSamba \
        -o APT::FTPArchive::Release::Label=HardenSamba \
        -o "APT::FTPArchive::Release::Suite=$suite" \
        -o "APT::FTPArchive::Release::Codename=$suite" \
        -o "APT::FTPArchive::Release::Architectures=all $EMPTY_ARCHITECTURES" \
        -o "APT::FTPArchive::Release::Components=$COMPONENT" \
        release "dists/$suite" > ".release.$suite"
    mv ".release.$suite" "dists/$suite/Release"
    if [ -n "$KEY" ]; then
        gpg --batch --yes --local-user "$KEY" --digest-algo SHA256 --armor --clearsign \
            --output "dists/$suite/InRelease" "dists/$suite/Release"
        gpg --batch --yes --local-user "$KEY" --digest-algo SHA256 --armor --detach-sign \
            --output "dists/$suite/Release.gpg" "dists/$suite/Release"
    fi
    echo "published $suite: $(grep -c '^Package: ' "dists/$suite/$COMPONENT/binary-all/Packages") package(s)"
done
