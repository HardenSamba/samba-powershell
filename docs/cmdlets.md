# Cmdlet surface

## What this document covers

The read cmdlets of ticket #3. Four are implemented end to end:

| Cmdlet | Returns | Backend operation |
|---|---|---|
| `Get-ADUser` | `SambaAD.User` | `get_ad_user` |
| `Get-ADComputer` | `SambaAD.Computer` | `get_ad_computer` |
| `Get-ADGroup` | `SambaAD.Group` | `get_ad_group` |
| `Get-ADObject` | `SambaAD.Object` | `get_ad_object` |

Each takes `-Identity` (a distinguished name — see below), `-Server` (or the
`SAMBA_AD_SERVER` environment variable) and `-Properties`. Each returns a typed
object the format file renders as a table, and each writes a non-terminating
`ErrorRecord` on failure so a pipeline under `-ErrorAction SilentlyContinue`
continues. A cmdlet given an object of another class — `Get-ADUser` on a group —
reports `SambaAD.ObjectNotFound`, the way Windows reports it, rather than
finding the object and complaining about its type.

The translation, conversion and identity rules below are implemented and tested
offline, with no directory reachable. The search parameters that would carry
them to a server are listed as unsupported at the end, because the client
exposed by `samba-adws` currently offers a read by distinguished name and no
enumeration. That client API is tracked in
[samba-adws#7](https://github.com/HardenSamba/samba-adws/issues/7).

## Where values are converted

In Python, once, in `src/samba_powershell/values/`. The backend already owns
the shape of the JSON response, so converting there keeps one implementation,
lets the conversions be tested without `pwsh`, and hands PowerShell values that
are already typed. The PowerShell half formats; it does not decode.

## Identity resolution

`-Identity` is classified by its own shape, in this order.

| Form | Recognised by | Matched against |
|---|---|---|
| SID | `S-1-` followed by numeric parts | `objectSid`, textual form |
| GUID | eight-four-four-four-twelve hex digits | `objectGUID`, escaped little-endian bytes |
| Distinguished name | a leading `attribute=` component | `distinguishedName` |
| Account name | anything else | `sAMAccountName` |

A GUID cannot travel as text: the directory stores it little-endian, so the
filter carries the byte sequence rather than the printed form.

**Live, only the distinguished name form reaches the wire.** The other three
forms require matching a filter against the directory, which needs the
enumeration the supported client does not offer yet. A cmdlet given a
sAMAccountName, SID or GUID identity refuses with
`SambaAD.IdentityNotResolvable` and says to give a distinguished name — a
stated gap rather than an enumeration that silently does not happen. The
classification and the filters each form implies are implemented and tested,
so resolution lights up when the client gains enumeration.

When an identity matches nothing, the cmdlet writes a non-terminating
`ErrorRecord` whose `FullyQualifiedErrorId` is `SambaAD.ObjectNotFound` and
whose `TargetObject` is the identity, so a pipeline under
`-ErrorAction SilentlyContinue` continues. When an identity matches more than
one object, the cmdlet fails with `SambaAD.IdentityNotUnique` rather than
choosing one, because silently picking a match would make the result depend on
directory ordering.

## Filter operators

`-Filter` is its own small expression language, not PowerShell code. It is
parsed in Python and every operator below is covered by a test table. An
unsupported construct raises an error naming it and never produces a filter.

| PowerShell | LDAP form |
|---|---|
| `-eq` | `(attr=value)`, or `(!(attr=*))` when the value is `$null` |
| `-ne` | `(!(attr=value))`, or `(attr=*)` when the value is `$null` |
| `-lt` | `(!(attr>=value))` |
| `-le` | `(attr<=value)` |
| `-gt` | `(!(attr<=value))` |
| `-ge` | `(attr>=value)` |
| `-like` | `(attr=pattern)`, `*` kept as the wildcard |
| `-notlike` | `(!(attr=pattern))` |
| `-approx` | `(attr~=value)` |
| `-band` | `(attr:1.2.840.113556.1.4.803:=value)` |
| `-bor` | `(attr:1.2.840.113556.1.4.804:=value)` |
| `-recursivematch` | `(attr:1.2.840.113556.1.4.1941:=value)` |
| `-and` | `(&...)` |
| `-or` | `(|...)` |
| `-not` | `(!...)` |

LDAP offers no strict comparison, so `-lt` and `-gt` are the negation of the
inclusive form. The three matching-rule identifiers are the ones published in
MS-ADTS; none is invented here.

`-not` binds tightest, then `-and`, then `-or`. Parentheses override that.

Every interpolated value is escaped per RFC 4515 section 3: `\`, `*`, `(`, `)`
and NUL become their hex escapes. This is the injection surface of the module,
so a value containing `*` and `)` is matched literally and cannot close its own
assertion. Under `-like` alone, `*` stays a wildcard while its neighbours are
still escaped. Attribute names are checked against the RFC 4512 spelling rather
than interpolated unchecked.

## Value conversions

| Attribute kind | Stored as | Returned as |
|---|---|---|
| `objectSid` | binary, MS-DTYP layout | `S-1-5-21-...` text |
| `objectGUID` | binary, first three fields little-endian | GUID text |
| `whenCreated`, `whenChanged` | generalised time | timezone-aware datetime |
| `pwdLastSet`, `accountExpires`, `lastLogonTimestamp` | 100-nanosecond intervals since 1601 | datetime, or nothing |
| `Enabled` | not stored | derived from `userAccountControl` |

Both `0` and `0x7FFFFFFFFFFFFFFF` are sentinels meaning "never", not dates at
either end of the range, and decode to nothing rather than to a year 1601 or
30828 timestamp.

`Enabled` is not a directory attribute. It is the `ACCOUNTDISABLE` bit `0x2` of
`userAccountControl`, read the other way round. Contract 6.1 forbids inventing
an attribute for it, and a divergent schema stops a Windows controller
replicating.

## Default property sets

Returned when `-Properties` is absent. `-Properties` adds to this set; it does
not replace it, which is the behaviour administrators already expect.

| Cmdlet | Default properties | State |
|---|---|---|
| `Get-ADUser` | DistinguishedName, Enabled, GivenName, Name, ObjectClass, ObjectGUID, SamAccountName, SID, Surname, UserPrincipalName | decided |
| `Get-ADComputer` | DistinguishedName, DNSHostName, Enabled, Name, ObjectClass, ObjectGUID, SamAccountName, SID | decided |
| `Get-ADGroup` | DistinguishedName, GroupCategory, GroupScope, Name, ObjectClass, ObjectGUID, SamAccountName, SID | decided |
| `Get-ADObject` | DistinguishedName, Name, ObjectClass, ObjectGUID | decided |

Constructed attributes such as `tokenGroups` and `canonicalName` are computed
by the server and returned only when asked for by name. They do not appear
under `-Properties *`.

How the answer is rendered, in Python, before it crosses the JSON boundary:

- The default set's attributes appear under their PowerShell names —
  `sn` as `Surname`, `objectSid` as `SID`, `dNSHostName` as `DNSHostName`.
  An extra attribute asked for by name keeps its LDAP display name, which is
  what Windows does with `-Properties mail`.
- `Enabled`, `GroupCategory` and `GroupScope` are derived from
  `userAccountControl` and `groupType`, which are fetched in their place and
  shown raw only when asked for by name.
- `objectClass` reduces to the class the object is: the directory returns the
  hierarchy from `top` downwards, and the last value is the object's own class.
- `objectGUID` and `objectSid` are decoded from their binary forms; any other
  binary value is base64 text rather than a decode guess.
- Multi-valued attributes are lists. Everything in the rendered object survives
  JSON, because JSON is the channel it crosses to PowerShell.

## Not supported yet

These are parsed and translated, but no cmdlet accepts them, because the
supported client offers no enumeration to carry them to a server.

- `-Filter` and `-LDAPFilter`
- `-SearchBase` and `-SearchScope`
- `-ResultPageSize`, and therefore paged results

Paging goes through WS-Enumeration `Pull` carrying the LDAP paging control,
specified in MS-WSPELD. A default page size that silently truncates is the
classic failure here and it looks like success, so the count must be checked
against the same query run through `ldbsearch` before paging is claimed.

The cmdlets beyond `Get-ADUser` are not implemented. `Get-ADUser` currently
accepts a distinguished name only, resolves nothing else, and reads through
`get_by_dn`.
