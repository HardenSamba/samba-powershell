# samba-powershell

> PowerShell on Linux for Samba Active Directory administration.

Administering a Samba Active Directory domain from a terminal today means
`samba-tool`, `ldbsearch` and raw LDAP filters. Every administrator who came
from Windows already knows a different vocabulary: `Get-ADUser`, `New-ADGroup`,
`Set-ADAccountPassword`. Those cmdlets do not exist outside Windows, so a
Windows machine ends up wired into workflows that otherwise have no reason to
need one, and years of existing administration scripts cannot be reused. This
module aims to close that gap: the familiar cmdlet surface, running on Debian,
speaking to a Samba domain controller.

## Status

**Read cmdlets working against a live domain; not a packaged release.**
`Get-ADUser`, `Get-ADComputer`, `Get-ADGroup` and `Get-ADObject` read a Samba
domain through the `samba-adws` client. They have been checked on a Samba 4.17
controller running samba-adws 1.0.1, value by value against `ldbsearch`. They
install as a Debian package or through `install.sh`, both checked in CI. The
write cmdlets are not done, and the package is not published yet.

What is actually in this repository today:

| Present | Absent |
|---|---|
| A typed Python backend and JSON envelope | The write cmdlet surface |
| A `SambaAD` PowerShell module with four read cmdlets | `-Filter`, `-LDAPFilter`, `-SearchBase` and paging |
| Identity by distinguished name, GUID, SID or account name | A package published to the ecosystem archive |
| Offline Python and PowerShell tests, and a live acceptance harness | Any contract or coding standard check in CI |
| Debian packaging under `debian/`, and `install.sh` for a system without the archive | A configuration file, or code that reads one |
| A CI workflow on plain Debian: `mypy --strict`, pytest, the PowerShell tests, and the package built, linted, installed and purged | |
| `MODULE.yaml`, declaring the intended surface | |

The module is split between a PowerShell cmdlet surface and a Python backend,
and the two halves talk across a process boundary. `docs/architecture.md`
records how they talk and what that costs; `docs/cmdlets.md` records what each
cmdlet accepts and returns.

Work is tracked in the
[issue tracker](https://github.com/HardenSamba/samba-powershell/issues), in this
order: architecture decision, read cmdlets, write cmdlets, installable module
with tab completion.

## What it does

Four read cmdlets exist today. `Get-ADUser`, `Get-ADComputer` and `Get-ADGroup`
take an identity as a distinguished name, a GUID, a SID or an account name;
`Get-ADObject` takes a distinguished name, a GUID or a SID, as on Windows. Each
returns a typed object carrying the default properties the Windows module
returns, every one present even when unset. `-Properties` adds attributes,
typed by the schema; `-Properties *` returns every stored attribute. Objects
pipe into the next cmdlet by their `DistinguishedName`, and failures are
`ErrorRecord`s with stable `SambaAD.*` identifiers.

The completed module will provide:

- **Read cmdlets.** `Get-ADUser`, `Get-ADComputer`, `Get-ADGroup`,
  `Get-ADObject`, `Get-ADDomain` and the surrounding query surface. These cover
  most day-to-day use. Returned objects will carry the properties existing
  scripts expect, and filtering and paging will work on directories large enough
  that returning everything is not an option.
- **Write cmdlets.** Creating, modifying and removing objects, and setting
  passwords. Confirmation prompts and `-WhatIf` will behave the way a PowerShell
  user expects rather than approximately. Directory errors will surface as
  messages an operator can act on, not as a stack trace from the transport
  layer.
- **A Python backend.** The logic lives in Python, per the ecosystem contract.
  Only the cmdlet surface is PowerShell, a language exception declared in
  `MODULE.yaml` for the plain reason that a PowerShell module cannot be written
  in Python.
- **Shell integration and tab completion**, so the module is usable
  interactively and not only from scripts.

What it will **not** do is speak the wire protocol itself. That is `samba-adws`,
and it already exists.

## Why it exists

There is no open source equivalent. This is not a claim that the existing tools
are bad; it is a claim about what they are for.

`samba-tool` is Samba's own administration command and it is capable, but its
model is Samba's, not Active Directory's. Commands are subcommand trees, output
is text meant for a human, and composing several operations means parsing that
text. `ldbsearch` and the LDAP command line tools go the other way: full
control, at the cost of writing raw filters and distinguished names by hand for
routine work.

So what administrators do today is one of three things. They keep a Windows
machine, joined to the domain, purely as an administration console, which means
maintaining a Windows licence and a Windows host in order to administer a Linux
server. They rewrite their existing `ActiveDirectory` module scripts against
`samba-tool` or python-ldap, which is a rewrite per script with no reuse. Or
they administer the domain by hand and accept that the work is not repeatable.

None of that is satisfactory for an organisation whose reason for running Samba
in the first place was to stop depending on Windows. The cmdlet surface is a de
facto standard that a large population already knows. Reimplementing it on
Linux, over a protocol implementation that is already working, removes the last
routine reason to keep a Windows box in the room.

## Requirements

Taken from `MODULE.yaml`, which is the authoritative declaration.

| Requirement | Value | Why |
|---|---|---|
| Operating system | Debian, plain | The module must install and run without the HardenSamba image |
| Python | 3.11 or later | Declared in `pyproject.toml`; the ecosystem targets the version in Debian stable |
| Samba AD domain | Required | The module administers a directory; it has nothing to do without one |
| Module dependency | `samba-adws` (depends), 1.0.0 or later | The cmdlets speak the Active Directory Web Services protocol, which that module implements; its search client resolves account names and reads the schema |
| Debian packages | `powershell` | The cmdlet surface is a PowerShell module and needs a PowerShell host |

**Installs on:** domain controller or workstation. It is a client-side tool, so
a workstation is the usual place. Installing it on the controller is supported,
for administering the machine you are logged into.

Two notes on that dependency list:

- `samba-adws` must be reachable. The cmdlets are a client. A domain controller
  running the ADWS service, on TCP 9389, is what they talk to.
- `powershell` is not in Debian stable. The package depends on it all the same
  and the documented source is Microsoft's APT repository;
  [`docs/packaging.md`](docs/packaging.md) gives the commands and the reasoning,
  and whether that satisfies contract rule 7.2 is open in
  [hardensamba-modulekit#6](https://github.com/HardenSamba/hardensamba-modulekit/issues/6).

## Installation

[`docs/packaging.md`](docs/packaging.md) covers both ways in full, and compares
them.

### The package

The ecosystem APT repository is `hardensamba-apt`, which does not publish
`samba-powershell` yet. Build the package from a checkout, then install it with
PowerShell and samba-adws already installed:

```bash
dpkg-buildpackage -us -uc -b
sudo apt install ../samba-powershell_0.1.0-1_all.deb
```

A new `pwsh` finds the cmdlets without `Import-Module`. `sudo apt purge
samba-powershell` removes everything it installed.

### Without the archive

`install.sh` installs the same module and backend under `/usr/local`, for a
system that cannot reach a package archive, and removes them again:

```bash
sudo sh install.sh
sudo sh install.sh --uninstall
```

### Straight from a checkout

The backend also runs from a checkout with no installation at all:

```bash
PYTHONPATH=src python3 -m samba_powershell.cli status
```

## Usage

### Backend status

```console
$ PYTHONPATH=src python3 -m samba_powershell.cli status
samba-ad-backend: ready
```

This is a local startup check only. It deliberately performs no network or
directory work; `Get-ADUser` exercises the request path described below.

```console
$ PYTHONPATH=src python3 -m samba_powershell.cli --help
usage: samba-ad-backend [-h] [--version] {request,status} ...

PowerShell backend for Samba Active Directory administration.

positional arguments:
  {request,status}
    request         read one JSON request from standard input
    status          report whether the backend can start

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
```

`Import-Module` remains a PowerShell command. The installed Python executable
is deliberately named `samba-ad-backend` and is an internal process boundary,
not an imitation shell command.

### Reading the directory

With `samba-ad-backend` on `PATH`, samba-adws installed and a Kerberos ticket
for the calling user (`kinit`), from a checkout:

```powershell
$env:PSModulePath = (Join-Path $PWD 'powershell') + `
  [IO.Path]::PathSeparator + $env:PSModulePath
$env:SAMBA_AD_SERVER = 'dc1.example.com'

Get-ADUser jdoe
Get-ADUser 'CN=Jane Doe,OU=Staff,DC=example,DC=com' -Properties mail, memberOf
Get-ADComputer PC01
Get-ADGroup 'Domain Admins' -Properties member
Get-ADObject 'OU=Staff,DC=example,DC=com' -Properties *
Get-ADUser jdoe | Get-ADObject -Properties whenChanged
```

`-Server` and `SAMBA_AD_SERVER` take the controller's DNS host name: Kerberos
authenticates `host/<name>`, so an IP address does not work.

For an offline checkout proof that creates its own temporary backend wrapper
and module path, run `pwsh -NoProfile -File tests/test_powershell.ps1
-PythonPath "$(command -v python3)"` from Bash.

Filters, paging and the write surface belong to the next tickets. Their target
syntax is:

```powershell
Get-ADUser -Filter 'Name -like "j*"' -Properties mail,memberOf
Get-ADGroupMember -Identity 'Domain Admins' -Recursive

New-ADUser -Name 'Jane Doe' -SamAccountName jdoe -Path 'OU=Staff,DC=example,DC=com'
Set-ADUser -Identity jdoe -Department Engineering
Set-ADAccountPassword -Identity jdoe -Reset
Remove-ADUser -Identity jdoe -WhatIf
```

Authentication follows the transport through the caller's existing Kerberos
ticket cache. The module carries no permission model of its own: samba-adws
runs every request as the principal that authenticated it
([`samba-adws#8`](https://github.com/HardenSamba/samba-adws/issues/8), fixed in
samba-adws 1.0.0). Reads are not yet filtered attribute by attribute on the
server ([`samba-adws#17`](https://github.com/HardenSamba/samba-adws/issues/17)),
so a caller can read attributes its ACLs hide over LDAP. No write surface is
considered safe or complete until #8 has a live allow/deny proof.

## Configuration

Configuration lives in `/etc/hardensamba/samba-powershell/`, which is the
`writes.config_dir` declared in `MODULE.yaml`. Per the ecosystem contract, the
module owns that directory and writes no configuration outside it (contract
3.3); every other path it writes, the module and the backend, is declared under
`writes.paths` (contract 2.3).

**Nothing reads a configuration file today.** The directory is declared, not
populated. The format is not settled either, so the example below is a proposal
attached to the architecture decision, not a documented interface. Do not write
this file expecting it to take effect.

```ini
# /etc/hardensamba/samba-powershell/samba-powershell.conf
# PROPOSED. Nothing parses this file yet.

[connection]
# Default domain controller for cmdlets invoked without -Server.
# Empty means: discover through DNS, as a Windows client would.
server =

# TCP port of the Active Directory Web Services endpoint on that
# controller. 9389 is the protocol default and there is rarely a
# reason to change it.
port = 9389

# Seconds to wait for a response before the cmdlet gives up.
timeout = 30

```

The default property set is deliberately not a configuration key. It is the
decided contract of `docs/cmdlets.md`: the defaults administrators know from
Windows, with `-Properties` adding to the set rather than replacing it. A knob
that changes it per machine would make the same script return different columns
on different controllers.

When configuration becomes real, the file will be marked as a Debian conffile so
administrator edits survive package upgrades, and every key will be documented
in `docs/` with its default.

## How it fits the ecosystem

HardenSamba is a set of independent modules rather than a monolith. Each one
installs on a plain Debian system, and each one declares what it needs and what
it touches in its `MODULE.yaml`.

**This module depends on `samba-adws`.** That module implements Active Directory
Web Services on TCP 9389: the .NET message framing, the GSSAPI security layer,
the binary WCF encoding and the WS-\* operations that the Windows
`ActiveDirectory` cmdlets speak. It is the working half of this pair. This
module is the client half, and its whole value proposition rests on that
protocol implementation already existing.

**Nothing currently declares a dependency on this module.** It sits at the edge
of the ecosystem, facing the operator. Checked against every sibling manifest.

**Deliberately out of scope**, because a sibling module owns it:

| Concern | Owner |
|---|---|
| The ADWS wire protocol | `samba-adws` |
| Provisioning the domain controller, and `smb.conf` | `samba-dc-role` |
| Replication and database health checks | `samba-domain-health` |
| Group Policy authoring, and applying policy on Linux | `samba-gpo-engine`, `gpo-agent-linux` |
| Certificate services and enrolment | `samba-adcs` |
| A graphical administration console | `hardensamba-webui` |
| Joining a Debian machine to the domain | `linux-domain-join` |
| Migration from a Microsoft forest | `ad-migration-toolkit` |
| Backup and restore of the domain | `samba-domain-backup` |
| Cross-module interoperability testing | `interop-test-suite` |
| The APT repository the package is published to | `hardensamba-apt` |

This module must never depend on `hardensamba`, the image itself. That direction
is forbidden by the contract: the image depends on modules, not the reverse. If
this module ever stops working on plain Debian, it is broken.

## Development

```bash
git clone https://github.com/HardenSamba/samba-powershell.git
cd samba-powershell

sudo apt install python3 python3-pytest python3-mypy git \
  python3-yaml python3-jsonschema

PYTHONPATH=src python3 -m pytest tests -q   # every test passes
mypy --strict src                           # Success: no issues found
```

`python3-yaml` and `python3-jsonschema` are there for `modulekit`, which needs
both and is not otherwise a dependency of this module.

Both contract checks must pass before a commit, and both pass today:

```bash
modulekit validate .              # the manifest and the write surface
modulekit lint src benchmarks     # production and benchmark Python
python3 -m modulekit.norms tests --require-headers \
  --max-functions 50 --max-classes 5
```

If `modulekit` is not installed, run it from a checkout:

```bash
git clone https://github.com/HardenSamba/hardensamba-modulekit /tmp/mk
PYTHONPATH=/tmp/mk/src python3 -m modulekit.cli validate .
PYTHONPATH=/tmp/mk/src python3 -m modulekit.cli lint src benchmarks
PYTHONPATH=/tmp/mk/src python3 -m modulekit.norms tests --require-headers \
  --max-functions 50 --max-classes 5
```

CI runs on `debian:stable`, never on a HardenSamba image. A test that only
passes with extra software installed is a defect in the test.

`.github/workflows/ci.yml` holds three jobs on `debian:stable`. `test` installs
`python3`, `python3-pytest` and `mypy`, then runs `mypy --strict src`,
`PYTHONPATH=src python3 -m pytest tests -q` and `benchmarks/transport.py`.
`powershell` installs PowerShell from Microsoft's repository, validates the
module manifest, and runs `tests/test_powershell.ps1`,
`tests/test_composition.ps1` and `benchmarks/transport.ps1`. `package` builds
the `.deb`, runs `lintian --fail-on error`, then installs, exercises and purges
the package and the `install.sh` installation in turn, as
[`docs/packaging.md`](docs/packaging.md) describes. Every step fails its job
when it fails, so a red run means a real failure. What no job does is check
the contract:

- `modulekit validate .` and `modulekit lint` are not run in CI. The contract
  job that ran the validator has been removed rather than repaired: it cloned
  `hardensamba-modulekit` anonymously, that repository is private and
  `GITHUB_TOKEN` is scoped to the repository running the workflow, so the clone
  failed on every run and the job died before it checked anything.
- The manifest, the write surface and the coding standard are now verified
  locally only: by `modulekit` on a developer machine, by the `check-standard`
  skill in `.claude/skills/` and by the `code-style-auditor` agent in
  `.claude/agents/`. Both remain normative; nothing on GitHub enforces them.
  Tracked in
  [HardenSamba/hardensamba#5](https://github.com/HardenSamba/hardensamba/issues/5).

No check gates a merge in any case. The organisation is on a free plan, where
private repositories cannot have branch protection or required status checks at
all, so a green tick has never been a condition of merging here. It means the
type checker, the Python tests and the two PowerShell test scripts passed, and
that the package built, passed lintian, and installed, worked and purged clean
in a fresh container, as did `install.sh`; nothing else.

### Layout

| Path | Contents |
|---|---|
| `MODULE.yaml` | The manifest. Authoritative for dependencies and the write surface |
| `CLAUDE.md` | Project instructions, restating the parts of the contract that bind here |
| `src/samba_powershell/` | Typed Python backend and lazy ADWS client adapter |
| `powershell/SambaAD/` | Module manifest, cmdlet surface and format data |
| `tests/` | Offline Python and PowerShell boundary tests |
| `benchmarks/` | Required process and Unix-socket transport prototypes |
| `docs/` | English architecture and behaviour documentation |
| `debian/` | Packaging. The reference installation method |
| `install.sh` | Manual installation under `/usr/local`, and its removal |
| `.github/workflows/` | CI on plain Debian: `mypy --strict`, pytest, the PowerShell tests and the package |
| `.claude/` | Agents and a skill for assisted development |

### Claude agents

Three agents in `.claude/agents/`, each read-only and each with one job:

- **`code-style-auditor`** runs `modulekit lint` over the working diff, then
  looks for what the linter cannot see: `Any` used to silence `mypy`, header
  comments that only restate the signature, inline comments inside a function
  body, mutable global state, and the runtime invariants from the contract. It
  reports violations with `file:line` and a fix. It never edits.
- **`doc-sync-auditor`** decides which changes in a diff are observable from
  outside the code, and whether the matching documentation moved with them. A
  new flag means `README.md` and `docs/`. A new written path means `MODULE.yaml`
  as well, or `modulekit validate` fails. Refactoring that changes nothing
  observable is explicitly not its business.
- **`test-runner`** runs the test ladder in order and stops at the first
  failure, because a failure low down makes everything above it meaningless. It
  leads its report with regressions, reports skips with their reason, and never
  reports green on a run that was incomplete.

There is also a `check-standard` skill in `.claude/skills/`, which is the short
path to the two `modulekit` checks.

## Contributing

The coding standard is
[section 8 of the module contract](https://github.com/HardenSamba/hardensamba-modulekit),
and it is checked by `modulekit lint`. It is not a review comment you can argue
with: the rules are mechanical and the checker decides. CI does not run the
linter at all, and no longer runs the validator either, so running both before
a commit is on you.

Three rules surprise people, so they are worth stating up front:

1. **A comment block above every class and every function**, one to three lines,
   immediately above the `def` or `class` and above any decorator. It says what
   the thing is for, not how it works. This is not optional and it is not a
   docstring. In exchange, there are no inline comments inside a function body:
   the names and the types carry the detail.
2. **Functions are twenty lines or fewer**, blank lines excluded, with at most
   two levels of nesting. A third level means the function should be split.
3. **One class and five functions maximum per file.** Adding a sixth function is
   the moment to ask what the file is for, which is the cheapest moment to ask.

Also: complete typing, with `mypy --strict` passing. Lines of one hundred
characters or fewer. No `import *`, no bare `except:`, no mutable default
argument. Constants `UPPER_CASE`, functions `snake_case`, classes `PascalCase`.

The rationale, if you want it, is in the contract itself. A twenty-line function
with two levels of nesting fits in one head at once, and the reader of a
directory service module is often not its author, and is often reading it during
an incident.

**Everything is in English**: code, identifiers, comments, documentation, commit
messages and issues. The one exception is a verbatim error message from a
client, which keeps its original language.

A behaviour change updates the documentation in the same change. That is what
`doc-sync-auditor` exists to catch.

Protocol work is grounded in published specifications: Microsoft Open
Specifications, RFCs, W3C recommendations. Contributions must not derive from
disassembled or otherwise obscure sources, and identifiers must not mirror the
internal naming of any proprietary implementation.

<!-- modulekit: allow-provenance-marker -->

The paragraph above states the provenance rule, and stating it trips the
scanner that enforces it. The marker on the line above is the exemption
`modulekit validate` provides for a file that discusses the rule rather than
breaks it. `CLAUDE.md` carries the same marker for the same reason.

## Licence

Proprietary. The terms are the HardenSamba Proprietary Software License,
version 1.0, in [`LICENSE`](LICENSE), which `debian/copyright` carries in full.

This is a greenfield module, not a fork. There is no upstream project, no
inherited licence and no divergence to describe. The closest reference points
are the published cmdlet surface of the Windows `ActiveDirectory` module and the
wire behaviour implemented in `samba-adws`, and neither is a code ancestor of
anything here.
