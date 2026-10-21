#!/bin/sh
#
# Installs and exercises the built package in a fresh debian:stable container,
# by the steps docs/packaging.md documents and nothing else, then the manual
# installation. CI runs it after ci_build.sh, in a new container:
#
#   docker run --rm -v "$PWD:/src" -w /src debian:stable sh tests/package/ci_install.sh
#
# The samba-adws repository is private, so dist/ holds an empty stand-in for
# it; python3-yaml is the one tool the checks themselves need.

set -eu
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl
. /etc/os-release
curl -fsSLo /tmp/packages-microsoft-prod.deb \
    "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb"
dpkg -i /tmp/packages-microsoft-prod.deb
apt-get update
apt-get install -y --no-install-recommends powershell

apt-get install -y --no-install-recommends ./dist/samba-adws_1.0.1_all.deb python3-yaml

deb=$(ls dist/samba-powershell_*_all.deb)
sh tests/test_package.sh deb "$deb"
sh tests/test_package.sh coexist "$deb"
sh tests/test_package.sh manual
