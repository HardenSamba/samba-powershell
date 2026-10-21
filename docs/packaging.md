# Packaging and installation

The module is two halves that install to different places: a Python backend,
which `pybuild` packages on its own, and the `SambaAD` PowerShell module, which
`pybuild` never sees. This document records where each half goes and why, how
to install it either way, and what the package and CI check.

## Requirements

| Requirement | Where it comes from |
|---|---|
| Debian 12 or later | the module targets Debian stable |
| Python 3.11 or later | Debian |
| PowerShell 7.4 or later, package `powershell` | Microsoft's APT repository, see below |
| samba-adws 1.0.0 or later | the `samba-adws` repository's own package |
| A reachable Samba AD domain controller running samba-adws | the domain |

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
install has neither `curl` nor the CA certificates, so they come first:

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
`install.sh` supports it; the package and samba-adws have not been tried there.

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

With PowerShell installed as above and the `samba-adws` package installed:

```bash
sudo apt install ./samba-powershell_0.1.0-1_all.deb
```

A new `pwsh` then finds the cmdlets without `Import-Module`:

```powershell
Get-Command Get-ADUser            # Source: SambaAD
Get-Module -ListAvailable SambaAD # ModuleBase: /usr/local/share/powershell/Modules/SambaAD
```

`sudo apt purge samba-powershell` removes everything, the link included.

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
launcher uses `/usr/bin/python3`, the interpreter the Debian packages of
samba-adws and samba install for. Before it reports success it checks its own
result: the launcher starts, and `pwsh`, if present, lists the module where it
was put. It warns, without failing, when `pwsh` or the samba-adws client is
missing, which the package would have pulled in as dependencies. Running it
again replaces the files with the checkout's.

### The two ways compared

| | Package | `install.sh` |
|---|---|---|
| Module | `/usr/share/samba-powershell/Modules/SambaAD`, linked from `/usr/local/share/powershell/Modules/SambaAD` | `/usr/local/share/powershell/Modules/SambaAD` |
| Backend | `/usr/lib/python3/dist-packages/samba_powershell`, launcher `/usr/bin/samba-ad-backend` | `/usr/local/lib/samba-powershell`, launcher `/usr/local/bin/samba-ad-backend` |
| PowerShell, samba-adws | installed as dependencies | checked for, with a warning |
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
every pull request, and fails when any step fails. It runs two `debian:stable`
containers in turn over the checkout, so the install test starts from a system
that never saw a build tool, without passing files between jobs.

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
2. The samba-adws repository is private and the workflow's token cannot reach
   it, so an empty stand-in package, `tests/package/samba-adws.equivs`, satisfies
   the dependency; the cmdlets then report the client missing, which the checks
   expect. `python3-yaml` is the one tool the checks themselves need.
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

The same script, run on a controller with the real samba-adws, expects the
backend to ask for a server instead of reporting the client missing; it has been
run that way on a Samba 4.17 controller with samba-adws 1.0.1, together with an
upgrade from an earlier build and the cmdlets run by an unprivileged user and
over a non-login `ssh` command.

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
