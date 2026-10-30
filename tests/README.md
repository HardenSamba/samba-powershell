Tests must run on a plain Debian system, without the HardenSamba image.

`test_package.sh` installs, exercises and removes the package and the
`install.sh` installation on a disposable Debian system, as root, with
PowerShell, `python3-ldap`, `libsasl2-modules-gssapi-mit` and `python3-yaml`
installed; its header lists the modes, and
`docs/packaging.md` says what each checks. It writes to the system, so run it
only where that is the point, as CI does in a fresh container through
`package/ci_install.sh`, after `package/ci_build.sh` built the package.

`test_gallery.ps1` publishes the module to a throwaway local repository and
installs it from there with `Install-PSResource` and with `Install-Module`, in a
throwaway home. `package/test_apt_archive.sh` publishes the package into a
signed archive and installs it through apt alone, and `package/ci_live.sh`
provisions a real domain in a container and runs the live test against it. All
three write to the system, so CI runs them in fresh containers.

`test_live.ps1` is the acceptance boundary for a provisioned Samba AD domain. It
writes nothing to the directory. Obtain a Kerberos ticket before starting
PowerShell; the script deliberately has no password parameter. With the package
installed, or `samba-ad-backend` on `PATH`:

```powershell
./tests/test_live.ps1 -Server dc1.hardensamba.test -SamAccountName Administrator `
  -ComputerName DC1 -IpAddress 192.0.2.10
```

From a checkout, with `python3-ldap` installed and no installation of the module,
`-BackendCommand` names one executable, not a shell command with arguments. The
module adds `request` itself, and the launcher forwards it and inherits
`KRB5CCNAME`:

```bash
printf '#!/bin/sh\nexec env PYTHONPATH="%s/src" /usr/bin/python3 -m samba_powershell.cli "$@"\n' \
  "$(pwd -P)" > /tmp/samba-ad-backend
chmod 0700 /tmp/samba-ad-backend
```

It checks identities in every form, value types, constructed and binary
attributes, the wildcard, groups, computers, the schema, and the failures a domain
can produce on demand: a missing object, a wrong class, an unknown property, no
server, a closed port, an unknown host and no ticket. Timeouts, refusals by the
directory, a session too weak and a missing library are covered only offline. It
does not replace the offline
boundary test.
