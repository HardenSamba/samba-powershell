# Cmdlet surface

## What this document covers

The read cmdlets of ticket #3. Four are implemented end to end:

| Cmdlet | Returns | Backend operation | Identity forms |
|---|---|---|---|
| `Get-ADUser` | `SambaAD.User` | `get_ad_user` | DN, GUID, SID, account name |
| `Get-ADComputer` | `SambaAD.Computer` | `get_ad_computer` | DN, GUID, SID, account name (`$` optional) |
| `Get-ADGroup` | `SambaAD.Group` | `get_ad_group` | DN, GUID, SID, account name |
| `Get-ADObject` | `SambaAD.Object` | `get_ad_object` | DN, GUID, SID |

Each takes `-Identity`, `-Server` (or the `SAMBA_AD_SERVER` environment
variable) and `-Properties`. Each returns a typed object the format file renders
as a table, and each writes a non-terminating `ErrorRecord` on failure so a
pipeline under `-ErrorAction SilentlyContinue` continues.

A cmdlet given an object of another class — `Get-ADUser` on a group — reports
`SambaAD.ObjectNotFound`, the way Windows reports it, rather than finding the
object and complaining about its type. `Get-ADUser` also refuses computers,
although the `computer` class derives from `user` in the schema: computers
belong to `Get-ADComputer`, as on Windows.

## The pipeline

`-Identity` binds from the pipeline by value, so distinguished names, GUIDs,
SIDs and account names can be piped as strings, and by property name through
its `DistinguishedName` alias, so any object carrying a `DistinguishedName`
property binds — the cmdlets' own output included:

```powershell
Get-ADUser jdoe | Get-ADObject -Properties whenChanged
Get-ADGroup 'Domain Admins' -Properties member |
    Select-Object -ExpandProperty member | Get-ADUser -ErrorAction SilentlyContinue
```

A returned object converts to its distinguished name as a string, as a Windows
`ADObject` does, so `"$user"` is the DN.

Each object costs one backend process and at least one ADWS exchange, about
0.4 s on a controller on the local network, so a long pipeline is paced by
that rather than by PowerShell. Streaming several objects into `Format-Table`
fixes its column widths from the first rows; collect the results or use
`-AutoSize` when the widths matter.

## Error preference

The cmdlets honour `$ErrorActionPreference` as the caller set it, in the
caller's own scope: a script that sets `'Stop'` at its top stops on a missing
object, exactly as it would with the Windows module. An explicit
`-ErrorAction` still takes precedence. A script module would otherwise read
the preference from its own scope only, which is the PowerShell behaviour the
cmdlets work around.

## Where values are converted

In Python, once, in `src/samba_powershell/values/`. The backend already owns
the shape of the JSON response, so converting there keeps one implementation,
lets the conversions be tested without `pwsh`, and hands PowerShell values that
are already typed. The PowerShell half formats; it does not decode.

## Identity resolution

`-Identity` is classified by its own shape, in this order, after the
whitespace around it is dropped.

| Form | Recognised by | Reaches the directory as |
|---|---|---|
| Extended reference | `<GUID=...>` or `<SID=...>` | itself |
| SID | `S-1-` followed by numeric parts | `<SID=S-1-...>` |
| GUID | eight-four-four-four-twelve hex digits, braces optional | `<GUID=...>` |
| Distinguished name | a leading `attribute=` component | itself, once it parses |
| Account name | anything else | a `sAMAccountName` search |

The extended forms are LDAP's own: the directory resolves `<SID=...>` and
`<GUID=...>` to the object itself, so a SID or a GUID costs no search. A
distinguished name that does not parse — an empty component, an empty value, a
trailing lone backslash — is refused with `SambaAD.InvalidIdentity` before
anything travels, rather than answered with a not-found from a server that never
parsed it. The check is a lenient shape check, not the RFC 4514 grammar: it
accepts what ldb accepts, escaped characters, hex pairs, quoted values such as
`CN="Doe, Jane"`, multi-valued RDNs and spaces around `=`. An identity holding a
control character is refused the same way: the directory compares a value only
up to a NUL, so `Administrator` followed by a NUL and anything would otherwise
resolve to `Administrator`.

An account name is resolved the way Windows resolves it: a subtree search of
the domain's default naming context for that `sAMAccountName`, scoped to the
cmdlet's class, then a read of the one object found. `Get-ADComputer` also
matches the name with a trailing `$`, which a computer account carries and
Windows lets the caller leave out. `Get-ADObject` takes no account name, as on
Windows; it refuses one with `SambaAD.IdentityNotResolvable`, pointing at the
cmdlet that does.

When an identity matches nothing, or matches an object of another class, the
cmdlet writes a non-terminating `ErrorRecord` whose `FullyQualifiedErrorId` is
`SambaAD.ObjectNotFound`, whose `TargetObject` is the identity as the caller
gave it, less surrounding whitespace, and whose message is
`Cannot find an object with identity '<identity>'.`, whatever form the identity
took. When an account name matches more than one object, the cmdlet fails with
`SambaAD.IdentityNotUnique` rather than choosing one, because silently picking a
match would make the result depend on directory ordering.

For filters, the same classification also yields the LDAP assertion each form
implies; a GUID there travels as escaped little-endian bytes, because the
directory stores it that way. That half serves `-Filter` once it is wired.

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
than interpolated unchecked. The account-name search escapes the name the same
way.

## Value conversions

The endpoint carries every value as text or as base64. What an attribute holds
is decided by its syntax in the schema, which the backend reads for every
property asked for by name, in one search of the schema naming context.

| Attribute kind | Stored as | Returned as |
|---|---|---|
| `objectSid`, and any SID-syntax attribute such as `tokenGroups` | binary, MS-DTYP layout | `S-1-5-21-...` text |
| `objectGUID` | binary, first three fields little-endian | GUID text |
| Any other binary attribute | binary | base64 text |
| `whenCreated`, `whenChanged`, and any time-syntax attribute | generalised time | timezone-aware datetime |
| `pwdLastSet`, `accountExpires`, `lastLogonTimestamp`, `lastLogon`, `badPasswordTime`, `lockoutTime` | 100-nanosecond intervals since 1601 | datetime, or nothing |
| Integer and large-integer syntaxes, such as `userAccountControl` or `uSNChanged` | number | integer |
| Boolean syntax, such as `isCriticalSystemObject` | `TRUE` or `FALSE` | boolean |
| `Enabled` | not stored | derived from `userAccountControl` |
| `GroupCategory`, `GroupScope` | not stored | derived from `groupType` |

Both `0` and `0x7FFFFFFFFFFFFFFF` are sentinels meaning "never", not dates at
either end of the range, and decode to nothing rather than to a year 1601 or
30828 timestamp. A time-syntax value in the two-digit-year UTC-time form is left
as the server sent it rather than guessed at.

Times cross the JSON boundary as ISO 8601 text, and the response names the
properties that hold them; the module turns exactly those into local `DateTime`
values, as Windows shows them. Text that merely looks like a date — an `info` or
`extensionAttribute1` holding `2026-01-01T10:00:00Z` — stays text. That needs
`ConvertFrom-Json -DateKind`, which PowerShell 7.5 introduced; under 7.4,
`ConvertFrom-Json` itself turns any such text into a `DateTime`.

`Enabled` is not a directory attribute. It is the `ACCOUNTDISABLE` bit `0x2` of
`userAccountControl`, read the other way round. Contract 6.1 forbids inventing
an attribute for it, and a divergent schema stops a Windows controller
replicating.

An attribute the schema declares multi-valued is a list, even when it holds a
single value, and an empty list when it was asked for by name and holds none:
its shape never depends on how many values it has. `description` is the one
exception, in `Get-ADUser`, `Get-ADComputer` and `Get-ADGroup`: the schema
declares it multi-valued, but the directory keeps one value on the security
principals it manages, and those cmdlets on Windows show it as text.
`Get-ADObject` follows the schema for every object, users included, and returns
it as a list.

samba-adws 1.0.1 sends `objectClassCategory` of a `classSchema` object as a
boolean, which loses its value: the schema says Integer, the answer is `true` or
`false`, and the cmdlets pass that text through rather than invent a number. The
defect is the server's, and belongs to samba-adws to fix.

## Default property sets

Returned when `-Properties` is absent. `-Properties` adds to this set; it does
not replace it, which is the behaviour administrators already expect.

| Cmdlet | Default properties | State |
|---|---|---|
| `Get-ADUser` | DistinguishedName, Enabled, GivenName, Name, ObjectClass, ObjectGUID, SamAccountName, SID, Surname, UserPrincipalName | decided |
| `Get-ADComputer` | DistinguishedName, DNSHostName, Enabled, Name, ObjectClass, ObjectGUID, SamAccountName, SID | decided |
| `Get-ADGroup` | DistinguishedName, GroupCategory, GroupScope, Name, ObjectClass, ObjectGUID, SamAccountName, SID | decided |
| `Get-ADObject` | DistinguishedName, Name, ObjectClass, ObjectGUID | decided |

Every default property is present on every object, `$null` when the directory
holds no value for it — a user without a surname still has `Surname`. Every
property asked for by name is present the same way. One result set therefore
has one shape: `Set-StrictMode` scripts can read any property, and
`Export-Csv` or `Select-Object *`, which take their columns from the first
object, lose nothing from the objects after it.

How the answer is rendered, in Python, before it crosses the JSON boundary:

- The default set's attributes appear under their PowerShell names —
  `sn` as `Surname`, `objectSid` as `SID`, `dNSHostName` as `DNSHostName`.
  Asked for by name as well, or under `-Properties *`, such an attribute also
  keeps its LDAP name when the two differ by more than case, as Windows shows
  `sn` beside `Surname`.
- An attribute outside the cmdlet's default set keeps its LDAP display name,
  as the schema spells it, which is what Windows does with `-Properties mail`.
  `Get-ADObject -Properties objectSid` therefore shows `objectSid`, not `SID`.
- `Enabled`, `GroupCategory` and `GroupScope` are derived from
  `userAccountControl` and `groupType`, which are fetched in their place and
  shown raw only when asked for by name or under `-Properties *`.
- `objectClass` reduces to the class the object is: the directory returns the
  hierarchy from `top` downwards, and the last value is the object's own class.
- Properties are ordered by name without regard to case, as Windows lists them.
- Everything in the rendered object survives JSON, because JSON is the channel
  it crosses to PowerShell.

## -Properties

Each entry is one LDAP display name; `-Property` is an alias, as on Windows. A
name the schema does not define is refused with `SambaAD.InvalidProperty`, naming
every such name, the way Windows refuses it, rather than returning an object that
silently lacks it. A name that cannot be an attribute at all is refused before
anything travels: several names in one string (`'mail,memberOf'` rather than
`mail,memberOf`), or an attribute option such as `member;range=0-99`, which the
endpoint does not carry. Windows extended property names that are not
attributes, such as `EmailAddress` or `LastLogonDate`, are refused the same way;
ask for the attribute behind them. The cmdlet's own property names that are not
attributes — `SID`, `Surname`, `Enabled`, `GroupCategory`, `GroupScope` — are
accepted and ask for nothing more, since they are already shown. `-Properties`
given `$null` or an empty list is refused when PowerShell binds it, as on
Windows; leave the parameter out instead.

`-Properties *` reads the whole object and shows every attribute it stores,
the derivation sources included. Constructed attributes such as `tokenGroups`
and `canonicalName`, which the server computes on read, and the reference
attributes the endpoint adds of its own, do not appear under `-Properties *`;
name one beside the wildcard — `-Properties *,canonicalName` — to have it. A
named attribute the whole-object read did not return, such as
`msDS-KeyVersionNumber`, which the server computes only when named, is read
again in a second, projected exchange.

The schema is consulted only when a property is named or under the wildcard, so
a read of the default set costs one ADWS exchange. Naming properties adds a
RootDSE read and a schema search; an account-name identity adds a RootDSE read
and a search of its own.

## Servers and failures

`-Server` names the domain controller by its DNS host name. The transport
authenticates with Kerberos as the service `host/<name>`, so an IP address or an
alias has no principal to authenticate against. `host:port` reaches ADWS on
another port than 9389. A value of only whitespace is no server, and fails like
an absent one with `SambaAD.ServerRequired`.

A failure to reach or authenticate to the endpoint is reported against the
server as the caller gave it, port included, under the client's code
`SambaAD.TransportError`, with a category saying what failed and the usual cause
named:

| Category | When | The message adds |
|---|---|---|
| `AuthenticationError` | no Kerberos ticket | run `kinit`, or set `KRB5CCNAME` |
| `AuthenticationError` | no principal for the server name | use the DNS host name, not an IP or alias |
| `ConnectionError` | the name does not resolve | check `-Server` |
| `ConnectionError` | nothing listens on the port | check the port, or whether samba-adws runs |
| `OperationTimeout` | no answer within 30 seconds | |

A backend that is missing or has no execute bit reports
`SambaAD.BackendUnavailable`, and one that answers outside the protocol — no
JSON, another version, an exit code that disagrees with the answer, a result or
error missing a field the cmdlets read, property names that differ only in case
— reports `SambaAD.ProtocolError`. Both are non-terminating like every other
failure, each the one record in `-ErrorVariable`, and the backend's standard
error is written to the debug stream, shown with `-Debug`, rather than into the
message. A backend the system finds executable yet cannot start, such as a
script whose interpreter is gone, also reports `SambaAD.BackendUnavailable`, but
PowerShell leaves its own record of the failed start beside it.

## Not supported yet

These are parsed and translated, but no cmdlet accepts them yet. The
`samba-adws` search client the account-name lookup uses can carry them; wiring
them, with paging, is the next step of ticket #3.

- `-Filter` and `-LDAPFilter`
- `-SearchBase` and `-SearchScope`
- `-ResultPageSize`, and therefore paged results

Paging goes through WS-Enumeration `Pull` carrying the LDAP paging control,
specified in MS-WSPELD. A default page size that silently truncates is the
classic failure here and it looks like success, so the count must be checked
against the same query run through `ldbsearch` before paging is claimed.
