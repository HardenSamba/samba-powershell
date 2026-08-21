# Packaging

The module is two halves that install to different places, which is why the
naive `pybuild` package shipped nothing usable: it built the Python backend and
left the PowerShell module on the cutting-room floor.

## What the package installs

| Path | What | Placed by |
|---|---|---|
| `/usr/lib/python3/dist-packages/samba_powershell/` | The Python backend. | `pybuild` |
| `/usr/bin/samba-ad-backend` | The backend entry point the module runs. | the `samba-ad-backend` console script |
| `/usr/share/samba-powershell/SambaAD/` | The PowerShell module: `.psd1`, `.psm1`, the format file. | `debian/rules`, by hand |
| `/etc/profile.d/samba-powershell.sh` | Puts the module directory on `PSModulePath`. | `debian/rules` |

The PowerShell module is not Python, so `pybuild` never sees it.
`debian/rules` copies `powershell/SambaAD/` into the package in
`override_dh_auto_install`, and ships a `profile.d` snippet that prepends
`/usr/share/samba-powershell` to `PSModulePath` — the directory that *contains*
the `SambaAD` folder, which is what makes `Import-Module SambaAD` resolve.

## Building it

On a Debian or Ubuntu system, from the repository root:

```bash
sudo apt build-dep .        # or: debhelper-compat, dh-python, python3-all, python3-setuptools
dpkg-buildpackage -us -uc -b
dpkg-deb -c ../samba-powershell_*.deb        # list the contents
```

The build was run on Debian 12 and the resulting package's contents are recorded
in the pull request that added this file.

## Installing without the archive

`install.sh` at the repository root does the same by hand, for a system that
cannot reach the package archive. It is idempotent and installs the identical
files, with the backend entry point under `/usr/local/bin` rather than `/usr/bin`
so it does not collide with a later package.

## The unavoidable caveat: `powershell` is not in Debian stable

`debian/control` declares `Depends: powershell`, and PowerShell is **not** in the
Debian stable archive — it comes from Microsoft's own repository. Contract rule
7.2 requires runtime dependencies to be Debian stable packages, so this package
does not install from Debian stable alone. That is a real open point, not an
oversight: whether an external APT repository satisfies rule 7.2 is the owner's
decision, tracked in
[hardensamba-modulekit#6](https://github.com/HardenSamba/hardensamba-modulekit/issues/6).
Until it is settled, the package builds and its Python and module halves are
correct, but a controller needs PowerShell from Microsoft's repository for it to
run.

The `samba-adws` dependency, by contrast, is a HardenSamba module and installs
the ordinary way.

## Not yet done

`debian/copyright` still names no licence: the module's own code has no licence
statement, tracked in
[hardensamba-modulekit#5](https://github.com/HardenSamba/hardensamba-modulekit/issues/5).
The package is built as `UNRELEASED` and must not be published until that is
resolved.
