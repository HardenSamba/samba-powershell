#!/bin/sh
#
# Makes the key that signs the APT archive, stores it in the repository's
# "release" environment, and starts the release that publishes the archive. Run
# once, by the owner of the archive, on a machine where gh is logged in, after the
# release workflow reached the default branch:
#
#   sh tools/make_apt_signing_key.sh [tag]
#
# The environment only serves version tags and waits for the approval of whoever
# ran this, so a writer of the repository can neither read the key from a workflow
# of their own nor sign a release alone.
#
# The private key exists only in a temporary directory and in that secret. It is
# never printed and never kept here. Clients trust the public half, which the
# release publishes beside the archive, so replacing the key means every client
# fetches it again: this refuses to run when a key is already stored.

set -eu

REPOSITORY=HardenSamba/samba-powershell
ENVIRONMENT=release
TAG=${1:-v0.2.0}
IDENTITY='HardenSamba samba-powershell archive'

fail() {
    echo "make_apt_signing_key: $*" >&2
    exit 1
}

gh api "repos/$REPOSITORY/contents/.github/workflows/release.yml" >/dev/null 2>&1 \
    || fail "release.yml is not on the default branch of $REPOSITORY yet; merge it first."
if gh secret list --repo "$REPOSITORY" | grep -q '^APT_SIGNING_KEY'; then
    fail "a repository secret APT_SIGNING_KEY exists, which every writer can read. Remove it first: gh secret delete APT_SIGNING_KEY --repo $REPOSITORY"
fi
if gh secret list --repo "$REPOSITORY" --env "$ENVIRONMENT" 2>/dev/null | grep -q '^APT_SIGNING_KEY'; then
    fail "the $ENVIRONMENT environment already holds a key; delete it first to replace it."
fi

GNUPGHOME=$(mktemp -d)
export GNUPGHOME
trap 'gpgconf --kill all 2>/dev/null || true; rm -rf "$GNUPGHOME"' EXIT
# A fatal signal does not run the EXIT trap in every shell, and this directory is
# about to hold an unencrypted private key.
trap 'exit 1' HUP INT TERM
chmod 700 "$GNUPGHOME"
# chmod does nothing under Git Bash, where the directory inherits the ACL of %TEMP%.
if command -v icacls >/dev/null 2>&1 && command -v cygpath >/dev/null 2>&1; then
    icacls "$(cygpath -w "$GNUPGHOME")" /inheritance:r /grant:r "$USERNAME:(OI)(CI)F" >/dev/null
fi

printf '{"reviewers":[{"type":"User","id":%s}],"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}' \
    "$(gh api user --jq .id)" \
    | gh api -X PUT "repos/$REPOSITORY/environments/$ENVIRONMENT" --input - >/dev/null
gh api -X POST "repos/$REPOSITORY/environments/$ENVIRONMENT/deployment-branch-policies" \
    -f 'name=v*' -f type=tag >/dev/null

gpg --batch --quiet --passphrase '' --quick-generate-key "$IDENTITY" rsa4096 sign 5y
gpg --batch --armor --export-secret-keys "$IDENTITY" \
    | gh secret set APT_SIGNING_KEY --repo "$REPOSITORY" --env "$ENVIRONMENT"
echo "Signing key fingerprint, the one clients will trust:"
gpg --batch --list-keys --with-colons "$IDENTITY" | awk -F: '/^fpr:/ { print $10; exit }'

# Creating the tag is what starts the release; an existing one has to be asked.
if gh api "repos/$REPOSITORY/git/ref/tags/$TAG" >/dev/null 2>&1; then
    gh workflow run release.yml --repo "$REPOSITORY" --ref "$TAG"
else
    gh api -X POST "repos/$REPOSITORY/git/refs" -f "ref=refs/tags/$TAG" \
        -f "sha=$(gh api "repos/$REPOSITORY/git/ref/heads/main" --jq .object.sha)" >/dev/null
fi
echo "Release of $TAG started. Approve its deployments on the run's page:"
echo "  https://github.com/$REPOSITORY/actions/workflows/release.yml"
