# What a deletion preserves, and why this module will not pretend otherwise

A decision record. It answers issue #9 and constrains the removal commands of
issue #4: **on the Samba version this ecosystem targets, a deletion cannot be
faithfully restored by reanimating the tombstone, so this module will not ship a
`Restore-ADObject` that reanimates.** What it will ship, when the backend can
delete at all, is a removal that captures the object first and says plainly what
is lost.

## What was observed, not assumed

Established on the laboratory domain controller, Samba **4.17.12-Debian**, the
version this ecosystem targets. The commands and their output are recorded here
so the conclusion can be re-checked rather than trusted.

**The Recycle Bin optional feature is not enabled** (its default):

```
# ldbsearch -H sam.ldb -b "CN=Partitions,CN=Configuration,DC=hardensamba,DC=test" \
    '(msDS-EnabledFeature=*)' msDS-EnabledFeature
(no enabled optional features)
```

**A user, before deletion**, in two groups, with a mail address:

```
dn: CN=Del Probe,CN=Users,DC=hardensamba,DC=test
objectSid: S-1-5-21-...-1108
mail: del-probe@hardensamba.test
userAccountControl: 512
memberOf: CN=probe-grp-a,CN=Users,DC=hardensamba,DC=test
memberOf: CN=probe-grp-b,CN=Users,DC=hardensamba,DC=test
```

**The same object after `samba-tool user delete`**, read with `--show-deleted`:

```
dn: CN=Del Probe\0ADEL:...,CN=Deleted Objects,DC=hardensamba,DC=test
objectClass: top / person / organizationalPerson / user
instanceType, whenCreated, uSNCreated, objectGUID, objectSid,
sAMAccountName, userAccountControl,
isDeleted: TRUE
isRecycled: TRUE
lastKnownParent: CN=Users,DC=hardensamba,DC=test
cn, name (mangled with the DEL: GUID), whenChanged, uSNChanged
```

Everything else is gone: **`mail`, `givenName`, `sn` and every `memberOf` are not
on the tombstone.** `memberOf` is a computed back-link, so the deletion removed
the user from both groups the instant it landed.

The decisive field is **`isRecycled: TRUE`**, set immediately. Without the
Recycle Bin, Samba does not keep a recoverable tombstone phase; the object goes
straight to recycled, which is past the point where a faithful reanimation could
restore attributes.

**Reanimation returns an empty shell.** Removing `isDeleted` and setting a new DN
does bring the object back — and proves the point:

```
# (ldbmodify: delete isDeleted, replace distinguishedName ...)
Modified 1 records successfully
# ldbsearch '(sAMAccountName=del-probe)' mail givenName sn memberOf userAccountControl
dn: CN=Del Probe,CN=Users,DC=hardensamba,DC=test
userAccountControl: 512
# samba-tool group listmembers probe-grp-a
(empty)
```

The restored object has its name, its SID and `userAccountControl` — and nothing
else. No mail, no given name, no surname, and **no group memberships**: the
groups list it as a non-member. An administrator who ran this, saw the account
reappear and closed the incident would have restored an empty shell.

## The decisions

### 1. No `Restore-ADObject` that reanimates

A restore that returns the object above is worse than no restore, because it
consumes the incident in which the real information still existed elsewhere (a
backup, a `samba-domain-backup` snapshot). This module will not ship one. If a
restore command is ever offered, it restores from a capture this module took
(below), never from a bare tombstone reanimation, and it refuses — by name — an
object it did not capture.

### 2. No removal command ships before it can capture, and it cannot yet

The supported `samba-adws` client exposes **`get_by_dn` only** — no delete, no
modify. So `Remove-ADUser`/`Remove-ADGroup`/`Remove-ADObject` cannot reach the
directory at all today, independently of this decision. When issue #4 gains a
delete path (which needs `samba-adws` to expose one, and needs the authorization
fix tracked in samba-adws#8), the removal command must, before it deletes:

- read the full object as LDIF, and
- read and resolve `memberOf` into the concrete list of groups, **before** the
  delete lands, because that back-link is destroyed by the deletion,

or, if the capture cannot be taken, **warn and refuse rather than delete
silently**. The removal cmdlet's `-WhatIf`/`-Confirm` text must state, in the
administrator's own terms, that the deletion strips mail, given name, surname and
every group membership and that only a capture — not the directory — can bring
them back.

### 3. The capture is host-local sensitive state, and its store is unresolved

A capture written by this module lives on whichever controller ran the cmdlet. A
capture on `dc1` does not help an administrator restoring from `dc2`. That is the
per-controller-state problem
[hardensamba-modulekit#14](https://github.com/HardenSamba/hardensamba-modulekit/issues/14)
exists to answer, and this module has no answer of its own. Until it does, a
capture store is **not** shipped; the removal command warns (decision 2) rather
than promising a restore it cannot honour across controllers.

When a store is built, this record fixes its terms in advance:

- **Owner and mode:** `root`, `0600` files in a `0700` directory. A user's LDIF
  carries attributes an ordinary administrator has no reason to read, and
  credential-adjacent material.
- **Location:** under the module's own state directory, never inside a share.
- **Retention:** a bounded window enforced by something — a `systemd` timer or a
  purge on each run — not merely documented. A capture store with no expiry is a
  growing archive of deleted personal data, a liability, not a feature. It must
  be excluded from backups for the same reason.
- **Scope, stated honestly:** only deletions performed by this module are
  captured. An object deleted through `samba-tool`, `ldbdel`, an RSAT console or
  another module is not, and the restore command must say so rather than report
  an empty result.

### 4. The faithful path today

Until a capture store exists, the honest answer to "how do I get a deleted user
back with its memberships" is **not** this module. It is a restore from
`samba-domain-backup`, or enabling the AD Recycle Bin **before** the deletion —
which is a forest-wide, irreversible change (`samba-tool domain` enables it and
nothing disables it), and which this investigation deliberately did **not** make
on the shared laboratory. With the Recycle Bin enabled, `[MS-ADTS]` §3.1.1.5.5
specifies that the full attribute set is retained for `tombstoneLifetime`; that
is the specification, not something observed here, and the ecosystem should
verify it on this Samba version before relying on it.

## What the removal cmdlets must say to the operator

Written now so #4 inherits it as a requirement, not a discovery:

> `Remove-ADUser` deletes the account. On this domain the deletion cannot be
> faithfully undone: the account's mail, name attributes and **every group
> membership** are lost the moment it is deleted, and reanimating the tombstone
> brings back only an empty shell. To be able to restore it, take a
> `samba-domain-backup` first, or enable the AD Recycle Bin before deleting.
> This module does not capture the object yet — see docs/deletion.md.
