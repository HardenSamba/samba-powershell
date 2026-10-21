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

The backend reads through the supported client API of the server module,
delivered by [samba-adws#7](https://github.com/HardenSamba/samba-adws/issues/7):
`samba_adws.ADWSSearchClient`, which reads one object, names a naming context
and enumerates, with `samba_adws.search_query` to build a search. Both ship in
every packaged samba-adws release, 1.0.0 onwards, and are imported only when a
command reaches the network. Wire framing, WCF encoding and GSSAPI remain owned
by that module rather than copied here. The samba-adws Debian package exists
([samba-adws#6](https://github.com/HardenSamba/samba-adws/issues/6)), but the
HardenSamba archive does not publish it yet, so the declared package dependency
is satisfied by installing that package directly.

The client preserves the caller's Kerberos cache, and samba-adws runs every
request as the principal that authenticated it
([samba-adws#8](https://github.com/HardenSamba/samba-adws/issues/8), fixed in
samba-adws 1.0.0). Two limits remain on the server side. Reads are not filtered
attribute by attribute ([samba-adws#17](https://github.com/HardenSamba/samba-adws/issues/17)),
so a caller can read attributes its ACLs hide over LDAP, and no live allow/deny
test of #8 has been recorded. Write cmdlets remain blocked until it has.

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
Enumerate/Pull/Release. A read of the default set is one exchange; an
account-name identity or named properties add a RootDSE read and one search
each, every exchange its own connection, about 0.2 s apiece against a
controller on the local network. The decision can be revisited only with
measurements and without changing the JSON envelopes.

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

A successful response separates the PowerShell type name from its properties,
abridged here, and names the properties whose values are times:

```json
{
  "version": 1,
  "ok": true,
  "result": {
    "type": "SambaAD.User",
    "properties": {
      "DistinguishedName": "CN=Alice,DC=example,DC=com",
      "Name": "Alice",
      "whenCreated": "2024-02-29T12:00:00+00:00"
    },
    "datetimes": ["whenCreated"]
  }
}
```

Times travel as ISO 8601 text because JSON has no time type; `datetimes` is what
lets PowerShell turn exactly those into `DateTime` and leave any other text as
text. A reader of version 1 that ignores the field still gets every value.

Failures use a JSON envelope on standard output even when the process exits
non-zero:

```json
{
  "version": 1,
  "ok": false,
  "error": {
    "message": "Cannot find an object with identity 'alice'.",
    "error_id": "SambaAD.ObjectNotFound",
    "category": "ObjectNotFound",
    "target": "alice"
  }
}
```

PowerShell converts that envelope into an `ErrorRecord`. The `error_id` becomes
the `FullyQualifiedErrorId`, `category` maps to `ErrorCategory`, and `target`
becomes `TargetObject`. Python tracebacks are never part of the public channel.

Both halves pin the channel to UTF-8 rather than inheriting it. The backend
reconfigures its protocol streams and the PowerShell bridge sets the three
standard-stream encodings, so a directory value survives a caller locale such
as `LC_ALL=C`. Without that pin an accented value crosses the boundary
corrupted, or a valid request degrades into an untyped failure. Request bytes
that do not decode raise the same typed `SambaAD.InvalidRequest` error as
malformed JSON.

Objects become `PSCustomObject` instances whose first `PSTypeName` is the
response `type`, and whose `ToString()` is the distinguished name.
`powershell/SambaAD/SambaAD.Format.ps1xml` supplies the default table view, so
`Get-Member` sees properties rather than a JSON string. Which properties an
object carries, and how each value is converted, is decided in
[cmdlets.md](cmdlets.md).

A backend that cannot be started, or that answers outside the protocol, is
reported the same way as any other failure: a non-terminating `ErrorRecord`,
`SambaAD.BackendUnavailable` or `SambaAD.ProtocolError`. The bridge returns that
record rather than throwing it, because an exception caught on the way would
still be appended to the caller's `-ErrorVariable` beside the record. For the
same reason it checks what it can before acting — that the calling user can
execute the backend, asked through `test -x`; that the envelope parses, as a
hashtable, into every field the cmdlets read, with names an object can hold —
and writes the request through a task rather than a call that throws, so a
backend that exits before reading it is judged by its answer and its standard
error. What it cannot check beforehand, a script whose interpreter is gone,
still leaves PowerShell's own record of the failed start.

## Transport measurements

`benchmarks/transport.ps1` measures a real `Get-ADUser` call through the
PowerShell module and a resident Python Unix-socket prototype, without
directory or network work. The measured process is the shipped backend
entry point, with only the ADWS client replaced by the offline stub, so the
interpreter start being timed includes the real package import rather than
that of a bare fixture script. Run this exact command in a clean `debian:stable`
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
| `tests/test_composition.ps1` | The module driving the real backend, ADWS client stubbed |
| `benchmarks/transport.ps1` | PowerShell-to-Python acceptance measurements |
| `benchmarks/transport.py` | Lower-level transport reproducibility check |

On a lab workstation with a Kerberos ticket and samba-adws installed, the
end-to-end check from a checkout is:

```powershell
$env:SAMBA_AD_SERVER = 'dc1.example.com'
$env:PSModulePath = (Join-Path $PWD 'powershell') + `
  [IO.Path]::PathSeparator + $env:PSModulePath
Import-Module SambaAD
Get-ADUser alice | Get-Member
```

The offline test substitutes only the ADWS client boundary. A live run must be
reported separately and is not implied by passing unit tests.
