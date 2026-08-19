# Architecture

## Constraints

This module runs on a plain Debian domain controller or workstation. Its
Python backend may not use `pip` at installation or run time, and the
PowerShell surface is the only language exception allowed by contract 7.5.
The backend opens no Samba directory handle: it authenticates to `samba-adws`
on TCP 9389 as the calling user through that user's Kerberos credential cache.
It therefore neither imports `python3-samba` nor opens a `SamDB` locally.

PowerShell itself is not in the official Debian stable archive. It remains a
hard dependency because the module has no useful cmdlet surface without it.
The conflict between that fact and contracts 7.2 and 11.3 is tracked in
[hardensamba-modulekit#6](https://github.com/HardenSamba/hardensamba-modulekit/issues/6).
The package release remains blocked by that decision; this repository does not
silently weaken the relationship to `Recommends`.

The supported client API required from the server module is tracked in
[samba-adws#7](https://github.com/HardenSamba/samba-adws/issues/7). Wire framing,
WCF encoding and GSSAPI remain owned by that module rather than copied here.
Its installable Debian artefact is tracked separately in
[samba-adws#6](https://github.com/HardenSamba/samba-adws/issues/6). Until that
lands, the source proof may use the client checkout but the declared package
dependency cannot be satisfied from the HardenSamba archive.

## Chosen process boundary

Each cmdlet starts `samba-ad-backend request`, writes one versioned JSON object
to standard input and reads one JSON response from standard output. The
process inherits `KRB5CCNAME`, so the network identity is always the calling
user. Standard output is protocol-only; diagnostics belong on standard error.
No password is accepted in an argument, environment variable or JSON field.

The required process prototype initially put the request in a command-line
argument. The production bridge moves it to standard input because process
arguments are observable by other local tooling and have platform-dependent
size limits. That change does not alter the process lifetime being measured or
the JSON response, while it keeps identities and future write values out of
the process list.

The initial version deliberately chooses one process per invocation. It has a
measurable interpreter-start cost, but it has no daemon lifecycle, shared-user
state, stale socket or credential-cache ambiguity. A single backend invocation
may keep one ADWS connection for a multi-message operation such as
Enumerate/Pull/Release. The decision can be revisited only with measurements
and without changing the JSON envelopes.

The rejected prototype is a process resident for the PowerShell session,
speaking the same request-response JSON over a Unix-domain socket beneath the
caller's runtime directory. It is faster after startup, but needs ownership,
cleanup, crash recovery and per-user lifetime rules. Sharing such a process
between users is forbidden because it would share the wrong Kerberos identity.

## JSON protocol

Protocol version 1 accepts one request:

```json
{
  "version": 1,
  "operation": "get_ad_user",
  "parameters": {
    "identity": "CN=Alice,DC=example,DC=com",
    "server": "dc1.example.com",
    "properties": ["mail"]
  }
}
```

A successful response separates the PowerShell type name from its properties:

```json
{
  "version": 1,
  "ok": true,
  "result": {
    "type": "SambaAD.User",
    "properties": {
      "Name": "Alice",
      "DistinguishedName": "CN=Alice,DC=example,DC=com"
    }
  }
}
```

Failures use a JSON envelope on standard output even when the process exits
non-zero:

```json
{
  "version": 1,
  "ok": false,
  "error": {
    "message": "The directory object was not found.",
    "error_id": "SambaAD.IdentityNotFound",
    "category": "ObjectNotFound",
    "target": "alice"
  }
}
```

PowerShell converts that envelope into an `ErrorRecord`. The `error_id` becomes
the `FullyQualifiedErrorId`, `category` maps to `ErrorCategory`, and `target`
becomes `TargetObject`. Python tracebacks are never part of the public channel.

Objects become `PSCustomObject` instances whose first `PSTypeName` is the
response `type`. `powershell/SambaAD/SambaAD.Format.ps1xml` supplies the default
table view, so `Get-Member` sees properties rather than a JSON string.
The architecture proof requests only `distinguishedName`, `name`, and
`sAMAccountName` by default. Binary and time-valued attribute conversion is the
explicit value-shape decision in ticket #3; requesting those values is not
claimed by this ticket.

## Transport measurements

`benchmarks/transport.ps1` measures a real `Get-ADUser` call through the
PowerShell module and a resident Python Unix-socket prototype, without
directory or network work. Run this exact command in a clean `debian:stable`
environment after adding the PowerShell runtime described above:

```powershell
pwsh -NoProfile -File benchmarks/transport.ps1 `
  -PythonPath (Get-Command python3).Source
```

It measures the first request including Python startup and 100 sequential
`Get-ADUser` calls, each with a fresh backend. The socket row measures startup,
connection and its first exchange, followed by 100 warm exchanges over one
session-owned connection. `benchmarks/transport.py` preserves the required
argument-based process prototype as a lower-level reproducibility check. The
Debian measurements will be recorded here
from the CI run before this ticket is closed; host measurements are not
substituted for the acceptance environment.

| Transport | First call including startup | 100 sequential calls |
|---|---:|---:|
| Process per invocation | pending Debian CI | pending Debian CI |
| Resident Unix socket | pending Debian CI | pending Debian CI |

## Repository layout

| Path | Role |
|---|---|
| `powershell/SambaAD/SambaAD.psd1` | Module manifest and explicit exports |
| `powershell/SambaAD/SambaAD.psm1` | Public cmdlets and private process bridge |
| `powershell/SambaAD/SambaAD.Format.ps1xml` | Default typed-object formatting |
| `src/samba_powershell/` | Typed backend protocol, dispatch and ADWS adapter |
| `tests/` | Offline Python and PowerShell boundary tests |
| `benchmarks/transport.ps1` | PowerShell-to-Python acceptance measurements |
| `benchmarks/transport.py` | Lower-level transport reproducibility check |

The proof command currently accepts a distinguished name. Identity resolution
by GUID, SID and sAMAccountName belongs to ticket #3. On a lab workstation with
a Kerberos ticket and `samba-adws#7` installed, the end-to-end proof is:

```powershell
$env:SAMBA_AD_SERVER = 'dc1.example.com'
$env:PSModulePath = (Join-Path $PWD 'powershell') + `
  [IO.Path]::PathSeparator + $env:PSModulePath
Import-Module SambaAD
Get-ADUser 'CN=Alice,DC=example,DC=com' | Get-Member
```

The offline test substitutes only the ADWS client boundary. A live run must be
reported separately and is not implied by passing unit tests.
