Tests must run on a plain Debian system, without the HardenSamba image.

`test_live_adws.ps1` is the acceptance boundary for a provisioned Samba AD
domain and the supported `samba-adws` client, 1.0.0 or later. Obtain a Kerberos
ticket before starting PowerShell; the script deliberately has no password
parameter. Where the samba-adws package is installed, its client imports without
any path, and the launcher only needs this checkout's `src`. Otherwise pass a
backend launcher whose Python path contains both source trees:

From the `samba-powershell` checkout, with `samba-adws` checked out beside it,
create the source-only launcher as the same Unix account that will run
PowerShell:

```bash
powershell_source="$(pwd -P)"
adws_source="$(cd ../samba-adws && pwd -P)"
printf '%s\n' \
  '#!/bin/sh' \
  "exec /usr/bin/env PYTHONPATH=\"${powershell_source}/src:${adws_source}\" \
/usr/bin/python3 -m samba_powershell.cli \"\$@\"" \
  > /tmp/samba-ad-backend
chmod 0700 /tmp/samba-ad-backend
/tmp/samba-ad-backend status
```

The last command must print `samba-ad-backend: ready` without installing either
source tree.

`BackendCommand` must be the path to one executable, not a shell command with
arguments. The module adds `request` through `ProcessStartInfo.ArgumentList`;
the launcher forwards that argument unchanged and inherits `KRB5CCNAME`.

```powershell
./tests/test_live_adws.ps1 `
  -Server dc1.hardensamba.test `
  -Identity 'CN=live-reader,CN=Users,DC=hardensamba,DC=test' `
  -MissingIdentity 'CN=missing,CN=Users,DC=hardensamba,DC=test' `
  -ExpectedSamAccountName live-reader `
  -BackendCommand /tmp/samba-ad-backend
```

The proof checks a real typed object, its `Get-Member` property surface, and
the structured not-found `ErrorRecord`. It does not replace the offline
boundary test.
