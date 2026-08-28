# Architecture

## Constraints

This module runs on a plain Debian domain controller or workstation. Its
Python backend may not use `pip` at installation or run time, and the
PowerShell surface is the only language exception allowed by contract 7.5.
The backend opens no Samba directory handle: it authenticates to `samba-adws`
on TCP 9389 as the calling user through that user's Kerberos credential cache.
It therefore neither imports `python3-samba` nor opens a `SamDB` locally.
The backend is also single-threaded by construction: it imports no `threading`,
`asyncio`, `concurrent` or `multiprocessing` module, and its only module-level
bindings are immutable constants. One `samba-ad-backend request` process serves
exactly one request and then exits, so the prohibition in contract 5.1 on
threads around Samba handles holds structurally as well as vacuously, and no
request can observe state left in memory by another.

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

The client preserves the caller's Kerberos cache, but the current ADWS server
does not yet bind its accepted GSSAPI identity to the `SamDB` session. That
authorization flaw is tracked in
[samba-adws#8](https://github.com/HardenSamba/samba-adws/issues/8). A live read
can prove authentication and the end-to-end protocol, but it must not be cited
as proof that Samba evaluated the caller's ACLs. Write cmdlets remain blocked
until #8 has a live allow/deny test.

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

The initial version deliberately chooses one process per invocation. That costs
a measured 40.28 ms per call, the mean of 100 sequential `Get-ADUser` calls on
Debian stable in CI (see Transport measurements), but it has no daemon
lifecycle, shared-user state, stale socket or credential-cache ambiguity. A
single backend invocation may keep one ADWS connection for a multi-message
operation such as Enumerate/Pull/Release. The decision can be revisited only
with measurements and without changing the JSON envelopes.

The rejected prototype is a process resident for the PowerShell session,
speaking the same request-response JSON over a Unix-domain socket beneath the
caller's runtime directory. It is faster after startup, and its warm exchanges
measured 0.24 ms each, but that prototype echoes a line instead of serving a
request, so the figure is a transport floor rather than the cost of a resident
backend. It also needs ownership, cleanup, crash recovery and per-user lifetime
rules. Sharing such a process between users is forbidden because it would share
the wrong Kerberos identity.

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

Both halves pin the channel to UTF-8 rather than inheriting it. The backend
reconfigures its protocol streams and the PowerShell bridge sets the three
standard-stream encodings, so a directory value survives a caller locale such
as `LC_ALL=C`. Without that pin an accented value crosses the boundary
corrupted, or a valid request degrades into an untyped failure. Request bytes
that do not decode raise the same typed `SambaAD.InvalidRequest` error as
malformed JSON.

Objects become `PSCustomObject` instances whose first `PSTypeName` is the
response `type`. `powershell/SambaAD/SambaAD.Format.ps1xml` supplies the default
table view, so `Get-Member` sees properties rather than a JSON string.
The architecture proof requests only `distinguishedName`, `name`, and
`sAMAccountName` by default. Binary and time-valued attribute conversion is the
explicit value-shape decision in ticket #3; requesting those values is not
claimed by this ticket.

## Transport measurements

`benchmarks/transport.ps1` measures two transports, but it does not put the
same workload behind them, and that asymmetry is stated here because it governs
how the table must be read. The process row is a real `Get-ADUser` call through
the PowerShell module into the shipped backend entry point
(`python3 -m samba_powershell.cli`), with only the ADWS client replaced by the
offline stub, so the interpreter start being timed includes the real package
import. The socket row runs `benchmarks/echo_backend.py`, which binds a
Unix-domain socket and copies each line back verbatim: it never imports
`samba_powershell`, never parses JSON, never validates or dispatches a request,
and the PowerShell side checks the reply with a string comparison rather than
`ConvertFrom-Json`. Neither row does directory or network work. Run this command
in a clean `debian:stable` environment after adding the PowerShell runtime
described above:

```powershell
pwsh -NoProfile -File benchmarks/transport.ps1 `
  -PythonPath (Get-Command python3).Source
```

It measures the first request including Python startup and 100 sequential
`Get-ADUser` calls, each with a fresh backend. The socket row measures startup,
connection and its first exchange, followed by 100 warm exchanges over one
session-owned connection; its first-call figure also carries a socket-bind wait
polled at one-millisecond granularity. `benchmarks/transport.py` preserves the
required argument-based process prototype as a lower-level reproducibility
check, and it puts the same echo fixture behind both of its transports, so it
varies the transport alone.

The figures below come from CI run 32319045215, job `powershell`, on branch
`ticket/2` at `44257f3` on 2026-08-20. That job runs the script in a
`debian:stable` container on a GitHub `ubuntu-latest` runner, and the run
reported `Debian GNU/Linux 13 (trixie)`, PowerShell 7.6.5 and Python 3.13.5.
The step lives in `.github/workflows/ci.yml` and invokes the script through
`shell: pwsh`, which dot-sources it rather than using `-File`; the block above
is the equivalent reader-facing command, not the literal line CI ran. Host
measurements were not substituted for the acceptance environment, and the
values below are rounded from the JSON that run printed.

| Transport | First call including startup | 100 sequential calls (total / mean) |
|---|---:|---:|
| Process per invocation, full backend request | 92.1 ms | 4027.8 ms / 40.28 ms |
| Resident Unix socket, echo fixture only | 51.4 ms | 24.3 ms / 0.24 ms |

The two rows are not head to head, and the bias runs one way: the socket row
omits per-request work that a resident backend would still have to do, so it
flatters the rejected transport. The gap between the rows is an upper bound on
what a resident design could save, not an estimate of it. The bias does not
overturn the decision, because per-call interpreter start and package import
cost tens of milliseconds while the parsing, validation, dispatch and
serialisation the echo fixture skips cost well under one millisecond; but
0.24 ms is a transport floor and must not be quoted as the per-call cost of a
resident backend. Removing that confound needs a resident server doing the same
per-request work as `samba_powershell.cli`, and no such server exists: the
shipped backend has no resident mode.

These are single-run figures from a shared runner, not a stable benchmark.
Three further successful runs of the byte-identical script reported 89.2 ms,
101.6 ms and 122.5 ms for the process first call (runs 32319158550, 32319087489
and 32487513670), against 92.1 ms above, and 23.8 ms, 18.8 ms and 23.6 ms for
the socket 100-call total, against 24.3 ms. The process first call therefore
varies by about a third across runs while the ordering of the two transports
never changes, which is the only property the decision rests on.
`benchmarks/` is byte-identical across all four runs. `debian:stable` is a
floating tag, and PowerShell and Python are installed unpinned at run time, so
the environment above belongs to the cited run rather than to a fixed
acceptance image.

## Repository layout

| Path | Role |
|---|---|
| `powershell/SambaAD/SambaAD.psd1` | Module manifest and explicit exports |
| `powershell/SambaAD/SambaAD.psm1` | Public cmdlets and private process bridge |
| `powershell/SambaAD/SambaAD.Format.ps1xml` | Default typed-object formatting |
| `src/samba_powershell/` | Typed backend protocol, dispatch and ADWS adapter |
| `tests/` | Offline Python and PowerShell boundary tests |
| `tests/test_composition.ps1` | The module driving the real backend, ADWS client stubbed |
| `tests/test_live_adws.ps1` | Live-domain acceptance, operator-run and not in CI |
| `benchmarks/transport.ps1` | PowerShell-to-Python acceptance measurements |
| `benchmarks/transport.py` | Lower-level transport reproducibility check |
| `benchmarks/echo_backend.py` | Echo fixture behind the socket measurements |

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
reported separately and is not implied by passing unit tests. No workflow
invokes `tests/test_live_adws.ps1`: CI runs the offline PowerShell suites and
the benchmark only. That harness takes five mandatory parameters and has no
reachability guard, so it fails rather than skipping when no domain answers; an
operator with a lab runs it deliberately, following `tests/README.md` and
obtaining a Kerberos ticket before starting PowerShell.
