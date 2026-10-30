#!/bin/sh
#
# Builds and lints the package in a debian:stable container, from the checkout
# mounted at the working directory, and leaves the package in dist/. CI runs it
# as:
#
#   docker run --rm -v "$PWD:/src" -w /src debian:stable sh tests/package/ci_build.sh
#
# The build dependencies come from debian/control itself, so one missing there
# fails the build. lintian fails on any warning but the one docs/packaging.md
# justifies by name.

set -eu
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends lintian
apt-get build-dep -y --no-install-recommends ./
dpkg-buildpackage -us -uc -b
rm -rf dist
mkdir dist
mv ../samba-powershell_*.deb ../samba-powershell_*.buildinfo ../samba-powershell_*.changes dist/
dpkg-deb --info dist/samba-powershell_*.deb
dpkg-deb --contents dist/samba-powershell_*.deb
lintian --fail-on error,warning --display-info \
    --suppress-tags initial-upload-closes-no-bugs dist/samba-powershell_*.deb
