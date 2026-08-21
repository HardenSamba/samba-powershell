# The write commands

The counterparts to the read cmdlets: `New-ADUser`, `New-ADGroup`,
`New-ADOrganizationalUnit`, `Set-ADObject`, `Remove-ADObject`,
`Add-ADGroupMember`, `Remove-ADGroupMember`, `Enable-ADAccount`,
`Disable-ADAccount`, `Set-ADAccountPassword`, `Move-ADObject` and
`Rename-ADObject`.

## The state of the wire, stated first

**No write reaches a directory yet, and that is a limit of `samba-adws`, not of
this module.** The supported `samba_adws` client exposes `get_by_dn` only — no
create, modify, delete or set-password. Every write here is built and tested, and
every write refuses at run time with `SambaAD.WriteNotAvailable` until the client
gains the operation it needs. `samba-adws` also carries an authorization caveat
(its server runs directory operations as SYSTEM, tracked in samba-adws#8) that
must be resolved before writes are trusted against anything but a lab.

So this ticket delivers the whole write surface — the cmdlets, the confirmation
behaviour, the password handling, the fault mapping and the idempotency rules —
against the point where it plugs into `samba-adws`, and names exactly what
`samba-adws` must expose:

- `create(dn, attributes)`, `modify(dn, changes)`, `delete(dn)`,
  `set_password(dn, secret)` and `rename(dn, new_dn)` on the client, mapping onto
  the server handlers `samba-adws` already has (`create`, `modify`, `delete`,
  `set_password`).

`src/samba_powershell/write_protocol.py` is the exact contract.

## Where `-WhatIf` stops: in PowerShell

`-WhatIf` never reaches the network or the directory. Every write cmdlet declares
`[CmdletBinding(SupportsShouldProcess)]` and calls the backend only inside
`$PSCmdlet.ShouldProcess(...)`. A `-WhatIf` run returns before the backend
process is even started. This is proved by `tests/test_write_powershell.ps1`,
whose backend fixture **raises on any invocation**: a `-WhatIf` run that succeeds
proves nothing was started. The alternative — carrying a dry-run flag to the
backend — was rejected because it would still open the process and reach
`samba-adws`, which is exactly what `-WhatIf` promises not to do.

`ConfirmImpact` is `High` on `Remove-ADObject`, so it prompts by default;
`-Confirm:$false` silences it. It is `Medium` on the rest.

## The password never appears on a command line

`Set-ADAccountPassword` takes a `SecureString`. The secret is converted as late
as possible — immediately before the request is built — and handed to the backend
**inside the JSON request**, which crosses the process boundary on standard
input. It is never a command-line argument (`/proc/<pid>/cmdline` is
world-readable) and never an environment variable (inherited by every child). The
backend reads it from the request and passes it to the client's `set_password`;
it is never written to a log, and the module's own diagnostics carry the action,
not the value. A password refused by domain policy comes back as the client's
constraint-violation fault, translated to an `ErrorRecord` that names the policy
constraint rather than a generic failure — kept distinct because an administrator
needs to know "the policy rejected this" from "the call failed".

A create cannot smuggle a password in either: `Set-ADObject` and the create path
validate attributes to string lists and carry them verbatim, and the password has
its own operation. `unicodePwd` is not special-cased into a plaintext write.

## Idempotency: the reruns that decide whether a script is safe twice

- **`Add-ADGroupMember`** on a member already present changes nothing. The backend
  reads the current `member` set, and writes only when the set actually changes.
- **`Remove-ADGroupMember`** on a member already absent changes nothing, the same
  way.
- **`Enable-ADAccount`** / **`Disable-ADAccount`** read `userAccountControl`, flip
  only the `ACCOUNTDISABLE` bit, and write only when the bit actually changes, so
  the other flags are preserved and a rerun is a no-op.

Each of these is a read-modify-write on one client connection, and each no-op is
pinned by a test. Running the same provisioning twice makes no second change.

## Creating an enabled user is more than one operation

On Windows, an enabled user is created, then given a password, then has the
disabled bit cleared. Each is a separate directory write, and a later step can
fail after an earlier one succeeded. **This module does not hide that behind a
single cmdlet.** `New-ADUser` creates the object; setting a password is
`Set-ADAccountPassword`; enabling is `Enable-ADAccount`. Each is its own cmdlet
with its own confirmation and its own error, so a failure is attributed to the
step that failed and the operator is never left guessing which write half-ran.
A convenience `New-ADUser -AccountPassword -Enabled` that orchestrated all three
would have to define what it does when the password step fails after the object
exists — the orphan-account problem — and the honest answer for now, with no
transaction across `samba-adws` operations, is to keep the steps separate and
visible rather than to leave a half-created object behind a single call.

## Removal: read docs/deletion.md first

`Remove-ADObject` deletes, and on this Samba version a deletion cannot be
faithfully undone: mail, name attributes and every group membership are lost, and
reanimating the tombstone restores an empty shell (established empirically in
[docs/deletion.md](deletion.md)). The `-Confirm` prompt says so in the operator's
own terms. This module does **not** capture the object before deleting — a capture
store is per-controller state that
[hardensamba-modulekit#14](https://github.com/HardenSamba/hardensamba-modulekit/issues/14)
must resolve first — so the honest path to a restorable delete is a
`samba-domain-backup` beforehand, which the warning names.

## Faults become `ErrorRecord`s

Every backend fault carries a stable `error_id`, an `ErrorCategory` and a target,
and the PowerShell half turns it into a non-terminating `ErrorRecord` (via
`WriteError`), so a pipeline under `-ErrorAction SilentlyContinue` continues and a
script can inspect `$Error`. The write cmdlets do not `throw`; they write the
error and return, the same as the read cmdlets, which is what an administrator
expects from the `AD*` verbs.

## What is proven, and how

- The backend's write logic — what it asks the client, the idempotency no-ops, the
  refusal of a non-DN identity, and `WriteNotAvailable` against a read-only client
  — is proved offline in `tests/test_write.py` against a fake write client.
- The PowerShell `-WhatIf`/`-Confirm` behaviour is proved by
  `tests/test_write_powershell.ps1` against a backend that refuses to be reached.
- **Not proven, because `samba-adws` cannot carry a write:** an actual create,
  modify, delete or password change against a live directory. That lights up when
  `samba-adws` exposes the client operations `write_protocol.py` names and
  samba-adws#8 is resolved.
