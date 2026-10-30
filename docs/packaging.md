# Packaging and installation

The module is two halves that install to different places: a Python backend,
which `pybuild` packages on its own, and the `SambaAD` PowerShell module, which
`pybuild` never sees. This document records where each half goes and why, how
to install it each way, and what the package and CI check.

## Requirements

| Requirement | Where it comes from |
|---|---|
| Debian 12 or later | the module targets Debian stable |
| Python 3.11 or later | Debian |
| PowerShell 7.4 or later, package `powershell` | Microsoft's APT repository, see below |
| `python3-ldap`, `libsasl2-modules-gssapi-mit` | Debian |
| `krb5-user`, for `kinit` | Debian; the package recommends it, every other way must install it |
| A reachable Samba AD domain controller, TCP 389 | the domain |

## PowerShell is not in Debian stable

`apt-cache policy powershell` in a plain `debian:stable` container prints no
candidate: Debian does not carry PowerShell. Contract rule 7.2 requires runtime
dependencies to be Debian stable packages; whether an external repository
satisfies it is open in
[hardensamba-modulekit#6](https://github.com/HardenSamba/hardensamba-modulekit/issues/6).

The decision taken here is a hard `Depends: powershell` and a documented
third-party repository. A `Recommends` would let the package install without
the only host its module has, and leave a system that looks installed and cannot
run a single cmdlet. Microsoft publishes PowerShell for Debian in its own
repository, set up by the package it ships for that purpose. A default Debian
install has neither `curl` nor the CA certificates, so they come first. On a system
without `sudo`, run these as root and drop it:

```bash
sudo apt install ca-certificates curl
. /etc/os-release
curl -fsSLo /tmp/packages-microsoft-prod.deb \
  "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb"
sudo dpkg -i /tmp/packages-microsoft-prod.deb
sudo apt update
sudo apt install powershell
```

This is the same sequence the CI workflow runs, in a fresh `debian:stable`
container. Where a system cannot add a repository, the `.deb` Microsoft
publishes with each PowerShell release installs the same package through
`apt install ./powershell_*.deb`.

On Ubuntu 24.04 or later, the first release with Python 3.11 or later, the
repository package is under `config/ubuntu/${VERSION_ID}/` instead.
`install.sh` supports it; the package has not been tried there.

## Where the module goes

PowerShell looks for modules installed for every user in
`/usr/local/share/powershell/Modules`, which is on every `pwsh`'s default
`PSModulePath`. Debian policy keeps packages from shipping files under
`/usr/local`, so the package installs the module under `/usr/share` and its
maintainer scripts link it into that directory:

| Path | What | Placed by |
|---|---|---|
| `/usr/share/samba-powershell/Modules/SambaAD/` | the module: `.psd1`, `.psm1`, format file | `debian/rules` |
| `/usr/local/share/powershell/Modules/SambaAD` | a link to the directory above | `postinst`, removed by `postrm` |
| `/usr/lib/python3/dist-packages/samba_powershell/` | the Python backend | `pybuild` |
| `/usr/lib/python3/dist-packages/samba_powershell-*.dist-info/` | its metadata | `pybuild` |
| `/usr/bin/samba-ad-backend` | the backend the module starts | the console script |
| `/usr/share/man/man1/samba-ad-backend.1.gz` | its manual page | `dh_installman` |
| `/usr/share/doc/samba-powershell/` | changelog and copyright | debhelper |

The other option the ticket offered, a `profile.d` fragment adding
`/usr/share/samba-powershell/Modules` to `PSModulePath`, only reaches login
shells. A command run over `ssh host pwsh -c ...`, a cron job, a systemd unit,
or `sudo`, which resets the environment, would not find the module. The link is
on the path `pwsh` itself searches, so every one of those finds it, and the
package checks that.

The link is a deliberate deviation from Debian Policy 9.1.2, which keeps
packages from placing files under `/usr/local`, "either by putting them in the
file system archive to be unpacked by dpkg or by manipulating them in their
maintainer scripts". lintian cannot see what a maintainer script does, so its
silence says nothing about this. The trade-off is taken because the
alternative misses every non-login use of `pwsh`, and it is acceptable because
the package is published to the HardenSamba repository, not to Debian's. It is
the package's only footprint under `/usr/local`, and it is kept small:

- `postinst` creates the link and the directories leading to it, with mode
  0755 whatever the administrator's umask.
- It never replaces what an administrator put there. A real directory, such as
  a manual installation, and a link pointing anywhere else are left alone and
  reported.
- `postrm` removes the link on remove and on purge, only while it still points
  at the package's module, and removes the directories if nothing else is in
  them. Every path either one
writes is declared in `MODULE.yaml` under `writes.paths`, as contract 2.3
requires.

`/etc/hardensamba/samba-powershell/` is the declared configuration directory.
Nothing reads a configuration file yet, so the package installs nothing there
and has no conffile to register.

## Installing the package

**Not published yet:** the archive goes live with the first release, which needs
the owner's signing key. Until then use `install.sh` or a package built by hand.

The archive is signed and served from the `gh-pages` branch of this repository,
through GitHub Pages. With PowerShell's repository added as above, add it once
and install; apt pulls in PowerShell, `python3-ldap` and the SASL plugin:

```bash
curl -fsSL https://hardensamba.github.io/samba-powershell/hardensamba-samba-powershell.gpg \
  | sudo install -m 0644 /dev/stdin /usr/share/keyrings/hardensamba-samba-powershell.gpg
echo "deb [signed-by=/usr/share/keyrings/hardensamba-samba-powershell.gpg] https://hardensamba.github.io/samba-powershell $(. /etc/os-release; echo "$VERSION_CODENAME") main" \
  | sudo tee /etc/apt/sources.list.d/samba-powershell.list
sudo apt update
sudo apt install samba-powershell
```

The suites are `bookworm` and `trixie`. To install a package built by hand
instead, `sudo apt install ./samba-powershell_0.2.0-1_all.deb` resolves the same
dependencies.

A new `pwsh` then finds the cmdlets, with `Import-Module SambaAD` or without it:

```powershell
Get-Command Get-ADUser            # Source: SambaAD
Get-Module -ListAvailable SambaAD # ModuleBase: /usr/local/share/powershell/Modules/SambaAD
```

`sudo apt purge samba-powershell` removes everything, the link included.

## First use

The cmdlets need three things from the machine they run on, none of which the
packages can set up:

- **Kerberos configuration.** `krb5-user` asks for the realm and the KDC when it
  installs, unless the installation is noninteractive; otherwise write
  `/etc/krb5.conf` yourself.
- **DNS.** The controller's DNS host name must resolve, and clocks must be within
  Kerberos's tolerance, five minutes by default.
- **A ticket.** `kinit user@REALM`, then give the controller's name with `-Server`
  or `SAMBA_AD_SERVER`.

A name other than the controller's own works only as far as `krb5.conf` lets it:
Kerberos may canonicalize an alias or an address it can resolve in reverse. Use
the DNS host name; `dns_canonicalize_hostname = false` with `rdns = false` makes
the given name authoritative.

## Installing from the PowerShell Gallery

**Not published yet:** the module reaches the gallery with the first release made
with the owner's gallery API key.

```powershell
Install-Module SambaAD
Import-Module SambaAD
```

`Install-Module` copies one folder and nothing else, so the module published to
the gallery holds its backend inside it, under `backend/`, and runs it through
`/usr/bin/python3`, since unpacking drops execute bits.
`tools/build_gallery_module.sh` stages that folder. A gallery cannot install a
Debian package, so `python3-ldap`, `libsasl2-modules-gssapi-mit` and `krb5-user`
must be installed first, which contract rule 7.2 requires anyway; a cmdlet names
the first two when they are missing, with `SambaAD.ClientUnavailable`. On a system
without Python at all the same check reports `SambaAD.BackendUnavailable`, naming
the interpreter; installing `python3-ldap` brings it.

Use the package or the gallery on one system, not both. `Install-Module` declines
to install beside the package without `-Force`, and with it a user's own copy
shadows the package's. `-Scope AllUsers` would write through the package's link
into files dpkg owns.

## Publishing a release

Pushing a version tag runs `.github/workflows/release.yml`, in this order: merge
to the default branch, then tag. It refuses a tag that disagrees with any version
in the tree, builds and lints the package, adds it to the
pool on the `gh-pages` branch, regenerates and signs the indexes with
`tools/apt_publish.sh`, verifies them with the public key alone, and pushes the
branch. A version already published keeps its bytes. It then publishes the module
to the gallery.

It reads two secrets of the `release` environment, which belong to whoever owns
the archive and are never made by the workflow. That environment serves version
tags only and waits for the owner's approval of each job, so a writer of the
repository can neither read a key from a workflow of their own nor publish alone:

| Secret | What | How |
|---|---|---|
| `APT_SIGNING_KEY` | the private key that signs the archive; required | `sh tools/make_apt_signing_key.sh`, once the workflow is on the default branch, makes the environment and the key and starts the release |
| `PSGALLERY_API_KEY` | an API key of a gallery account; without it the gallery is skipped with a notice | `gh secret set PSGALLERY_API_KEY --repo HardenSamba/samba-powershell --env release` |

The ecosystem's own archive is `hardensamba-apt`, whose pipeline has no origin
yet and calls choosing one a decision for its owner. This archive uses the layout
that repository decided, `pool/main/<initial>/<source>/`, without its two
channels, so moving the package there later changes the client's source line and
nothing else. GitHub Pages serves a site only from a public repository on the
organisation's plan, which is why this repository is public. Pages caps a site at
1 GB and caches for ten minutes, so a new version can take that long to appear.

## Building it

On Debian, from the repository root:

```bash
sudo apt install build-essential debhelper dh-python pybuild-plugin-pyproject \
  python3-all python3-setuptools python3-pytest lintian
dpkg-buildpackage -us -uc -b
lintian ../samba-powershell_*.deb
```

The build runs the repository's test suite, `PYTHONPATH=src python3 -m pytest
tests`, unless `DEB_BUILD_OPTIONS=nocheck` is set. `pybuild-plugin-pyproject` is
required: the project has only a `pyproject.toml`, and `pybuild` cannot build it
without the plugin.

## Installing without the archive

`install.sh` at the repository root installs the same two halves by hand, for a
system that cannot reach the package archive. It writes only under
`/usr/local`, which Debian keeps for what the administrator installs by hand,
so it never touches a file dpkg owns:

| Path | What |
|---|---|
| `/usr/local/lib/samba-powershell/samba_powershell/` | the Python backend |
| `/usr/local/bin/samba-ad-backend` | its launcher |
| `/usr/local/share/powershell/Modules/SambaAD/` | the module, as a directory |

```bash
sudo sh install.sh               # install, or update to this checkout
sudo sh install.sh --uninstall   # remove it
```

It refuses to run while the package is installed, since both would answer to
the same command, and refuses while any link is where the module goes. Its
launcher uses `/usr/bin/python3`, the interpreter the Debian package of
python-ldap installs for. Before it reports success it checks its own
result: the launcher starts, and `pwsh`, if present, lists the module where it
was put. It warns, without failing, when `pwsh` or python-ldap is
missing, which the package would have pulled in as dependencies. Running it
again replaces the files with the checkout's.

### The two ways compared

| | Package | `install.sh` |
|---|---|---|
| Module | `/usr/share/samba-powershell/Modules/SambaAD`, linked from `/usr/local/share/powershell/Modules/SambaAD` | `/usr/local/share/powershell/Modules/SambaAD` |
| Backend | `/usr/lib/python3/dist-packages/samba_powershell`, launcher `/usr/bin/samba-ad-backend` | `/usr/local/lib/samba-powershell`, launcher `/usr/local/bin/samba-ad-backend` |
| PowerShell, python-ldap | installed as dependencies | checked for, with a warning |
| Byte-compiled Python | at install, by `dh_python3` | on first use |
| Update | `apt install` a newer package | run `install.sh` from a newer checkout |
| Removal | `apt purge samba-powershell` | `install.sh --uninstall` |
| Result | the same cmdlets, autoloaded by every `pwsh`, the same module listing path | the same |

The two cannot coexist: `install.sh` refuses to run beside the package. When
the package is installed over a manual installation, `postinst` leaves the
manual module directory in place and says so; `sh install.sh --uninstall`
then removes it, and `dpkg-reconfigure samba-powershell` links the packaged
module, which `install.sh --uninstall` reminds you of.

## What CI checks

The `package` job of `.github/workflows/ci.yml` runs on every push to `main` and
every pull request, and fails when any step fails. It runs `debian:stable`
containers in turn over the checkout, so each test starts from a system that never
saw a build tool, without passing files between jobs.

`tests/package/ci_build.sh`, in the first container, builds and lints:

1. The build dependencies are installed from `debian/control` itself, with
   `apt-get build-dep`, so one missing there fails the build.
2. `dpkg-buildpackage -us -uc -b` builds `samba-powershell_*_all.deb`, running
   the test suite.
3. lintian passes with `--fail-on error,warning`; the one warning justified
   below is suppressed by name, so any other fails the job until it is fixed or
   justified here.

`tests/package/ci_install.sh`, in a fresh container that holds only the built
packages and the checkout:

1. PowerShell is installed by the documented steps above, and nothing else.
2. `python3-ldap` and the SASL plugin are installed first, so the checks can tell
   what the package itself added. `python3-yaml` is the one tool the checks
   themselves need.
3. `tests/test_package.sh deb` checks the package's `Depends`, installs it under
   umask 077 and checks, in a fresh `pwsh` with no `Import-Module`, as root and
   as the unprivileged user `nobody`, that `Get-ADUser -<Tab>` completes
   `-Identity`, `-Server` and `-Properties` before anything loaded the module,
   that `Get-Command Get-ADUser` resolves to `SambaAD`, that
   `Get-Module -ListAvailable SambaAD` lists the module at the linked path, and
   that the backend answers. It compares with `MODULE.yaml`, through
   `tests/package_paths.py`, both `dpkg -L` and every path the installation
   added to `/usr`, `/etc`, `/opt`, `/srv` and `/var`, so a maintainer script's
   writes and directories are checked too. It checks that `install.sh` and
   `install.sh --uninstall` refuse to run beside the package, that
   `apt-get remove` removes the link, and that after `apt-get purge` the system
   holds nothing it did not hold before.
4. `tests/test_package.sh coexist` installs the package over a manual
   installation and checks the hand-over described above.
5. `tests/test_package.sh manual` does the same as `deb` with `install.sh`, run
   twice to prove it idempotent, checks that `install.sh` refuses to run as
   another user than root, and that `install.sh --uninstall` restores the
   system.

6. `tests/test_gallery.ps1` publishes the module to a throwaway local repository
   and installs it with `Install-PSResource` and with `Install-Module`, in a
   throwaway home, and runs the cmdlets from there.

`tests/package/test_apt_archive.sh`, in another fresh container with only
PowerShell's repository added, publishes the package into an archive signed with
a throwaway key, checks that apt refuses a tampered `InRelease`, and installs
through apt alone, which proves the `Depends` are complete.

`tests/package/ci_live.sh`, in a last privileged container, provisions a real
Samba domain with no samba-adws installed and nothing on the ADWS port, installs
the package, and runs `tests/test_live.ps1` and `tests/test_gallery.ps1` against
it, which proves the module needs nothing on a controller but Samba.

## lintian

lintian reports no error. One warning remains, the same on Debian 12 with
`--pedantic` and in CI's `debian:stable`:

| Tag | Why it stays |
|---|---|
| `initial-upload-closes-no-bugs` | Debian asks a first upload to its archive to close an ITP bug. This package is published to the HardenSamba repository by `hardensamba-apt`, not uploaded to Debian, so there is no ITP to close. |

## Not done yet

The ticket also asks for argument completers for `-Identity`, `-Properties` and
`-SearchBase`. Parameter names complete, which the acceptance check covers;
completing values does not yet, and is tracked in
[#18](https://github.com/HardenSamba/samba-powershell/issues/18). `-SearchBase` does not exist until the search
parameters land, and a `-Properties` completer needs the decided cache over the
schema rather than a directory query per keystroke.
