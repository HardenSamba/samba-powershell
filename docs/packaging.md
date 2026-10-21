# Packaging and installation

The module is two halves that install to different places: a Python backend,
which `pybuild` packages on its own, and the `SambaAD` PowerShell module, which
`pybuild` never sees. This document records where each half goes and why, how
to install it either way, and what the package and CI check.

## Requirements

| Requirement | Where it comes from |
|---|---|
| Debian 12 or later, or a derived Ubuntu | the module targets Debian stable |
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
repository, set up by the package it ships for that purpose:

```bash
. /etc/os-release
curl -fsSLo /tmp/packages-microsoft-prod.deb \
  "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb"
sudo dpkg -i /tmp/packages-microsoft-prod.deb
sudo apt update
sudo apt install powershell
```

This is the same sequence the CI workflow runs. Where a system cannot add a
repository, the `.deb` Microsoft publishes with each PowerShell release installs
the same package through `apt install ./powershell_*.deb`.

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

The link is the package's only footprint under `/usr/local`. `postinst` creates
it and the directories leading to it. It never replaces a real directory there,
such as a manual installation; it says so and leaves the directory alone.
`postrm` removes the link only while it still points at the package's module,
and removes the directories if nothing else is in them. Every path either one
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
the same command, and refuses while the package's link is still there. Before
it reports success it checks its own result: the launcher starts, and `pwsh`, if
present, lists the module where it was put. It warns, without failing, when
`pwsh` or the samba-adws client is missing, which the package would have pulled
in as dependencies. Running it again replaces the files with the checkout's.

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

The two cannot coexist: `install.sh` refuses to run beside the package, and the
package's `postinst` leaves a manual installation's module directory in place
and asks for `install.sh --uninstall`.

## What CI checks

The `package` job of `.github/workflows/ci.yml` runs in `debian:stable` on every
push to `main` and every pull request, and fails when any step fails:

1. `dpkg-buildpackage -us -uc -b` builds `samba-powershell_*_all.deb`, running
   the test suite.
2. `lintian --fail-on error` passes on the package.
3. PowerShell is installed from Microsoft's repository. The samba-adws
   repository is private and the workflow's token cannot reach it, so an empty
   stand-in package, `tests/package/samba-adws.equivs`, satisfies the dependency.
   The cmdlets then report the client missing, which the checks expect.
4. `tests/test_package.sh deb` installs the package and checks, in a fresh
   `pwsh` with no `Import-Module`, that `Get-Command Get-ADUser` resolves to
   `SambaAD`, that `Get-ADUser -<Tab>` completes `-Identity`, `-Server` and
   `-Properties`, that `Get-Module -ListAvailable SambaAD` lists the module at
   the linked path, and that the backend answers. It compares `dpkg -L` and the
   link with `MODULE.yaml` through `tests/package_paths.py`, checks that
   `install.sh` refuses to run beside the package, then purges it and checks
   that nothing of the module is left under `/usr` or `/etc`.
5. `tests/test_package.sh manual` does the same with `install.sh`, twice to
   prove it idempotent, compares every file it wrote with `MODULE.yaml`, and
   checks that `install.sh --uninstall` leaves nothing behind.

The same script, run on a controller with the real samba-adws, expects the
backend to ask for a server instead of reporting the client missing; it has been
run that way on a Samba 4.17 controller with samba-adws 1.0.1, together with an
upgrade from an earlier build and the cmdlets run by an unprivileged user and
over a non-login `ssh` command.

## lintian

lintian reports no error. One warning remains, with `--pedantic` and
`--display-info` on Debian 12:

| Tag | Why it stays |
|---|---|
| `initial-upload-closes-no-bugs` | Debian asks a first upload to its archive to close an ITP bug. This package is published to the HardenSamba repository by `hardensamba-apt`, not uploaded to Debian, so there is no ITP to close. |

## Not done yet

The ticket also asks for argument completers for `-Identity`, `-Properties` and
`-SearchBase`. Parameter names complete, which the acceptance check covers;
completing values does not yet. `-SearchBase` does not exist until the search
parameters land, and a `-Properties` completer needs the decided cache over the
schema rather than a directory query per keystroke.
