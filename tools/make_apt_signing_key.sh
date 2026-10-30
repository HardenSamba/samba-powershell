#!/bin/sh
#
# Makes the key that signs the APT archive, stores it as the repository's
# APT_SIGNING_KEY secret, and starts the release that publishes the archive. Run
# once, by the owner of the archive, on a machine where gh is logged in:
#
#   sh tools/make_apt_signing_key.sh [tag]
#
# The private key exists only in a temporary directory and in that secret. It is
# never printed and never kept here. Clients trust the public half, which the
# release publishes beside the archive, so replacing the key means every client
# fetches it again: this refuses to run when the secret already exists.

set -eu

REPOSITORY=HardenSamba/samba-powershell
TAG=${1:-v0.2.0}
IDENTITY='HardenSamba samba-powershell archive'

if gh secret list --repo "$REPOSITORY" | grep -q '^APT_SIGNING_KEY'; then
    echo "APT_SIGNING_KEY already exists on $REPOSITORY; delete it first to replace the key." >&2
    exit 1
fi

GNUPGHOME=$(mktemp -d)
export GNUPGHOME
trap 'gpgconf --kill all 2>/dev/null || true; rm -rf "$GNUPGHOME"' EXIT
chmod 700 "$GNUPGHOME"

gpg --batch --quiet --passphrase '' --quick-generate-key "$IDENTITY" rsa4096 sign 5y
gpg --batch --armor --export-secret-keys "$IDENTITY" \
    | gh secret set APT_SIGNING_KEY --repo "$REPOSITORY"
echo "Signing key fingerprint, the one clients will trust:"
gpg --batch --list-keys --with-colons "$IDENTITY" | awk -F: '/^fpr:/ { print $10; exit }'

gh workflow run release.yml --repo "$REPOSITORY" --ref "$TAG"
echo "Release of $TAG started: gh run list --repo $REPOSITORY --workflow release.yml"
