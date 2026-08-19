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

**Scaffold. Nothing works yet.** Do not install this expecting cmdlets.

What is actually in this repository today:

| Present | Absent |
|---|---|
| A Python package `samba_powershell` | Any PowerShell module |
| A CLI entry point that prints `not implemented yet` | Any cmdlet |
| Three smoke tests (package imports, `--version`, `status` runs) | Any connection to `samba-adws` |
| A Debian packaging skeleton under `debian/` | A built or published package |
| A CI workflow on plain Debian, running the contract check and pytest | An `install.sh`, and CI steps that fail the build when a check fails |
| `MODULE.yaml`, declaring the intended surface | A configuration file, or code that reads one |

The first working version is not the full cmdlet set. It is the architecture
decision plus a single proof. The module is split between a PowerShell cmdlet
surface and a Python backend, and the two halves have to talk across a process
boundary. How they talk, and what that costs in latency and in the fidelity of
error messages, is the question that has to be answered before anything else is
worth writing. The first release records that decision in `docs/architecture.md`
and demonstrates exactly one command working end to end against a real domain.

Work is tracked in the
[issue tracker](https://github.com/HardenSamba/samba-powershell/issues), in this
order: architecture decision, read cmdlets, write cmdlets, installable module
with tab completion.

## What it does

Today it prints that it is not implemented. Everything below is future tense and
none of it is built.

The module **will** provide:

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
| Module dependency | `samba-adws` (depends) | The cmdlets speak the Active Directory Web Services protocol, which that module implements |
| Debian packages | `powershell` | The cmdlet surface is a PowerShell module and needs a PowerShell host |

**Installs on:** domain controller or workstation. It is a client-side tool, so
a workstation is the usual place. Installing it on the controller is supported,
for administering the machine you are logged into.

Two honest notes on that dependency list:

- `samba-adws` must be reachable. The cmdlets are a client. A domain controller
  running the ADWS service, on TCP 9389, is what they talk to.
- The manifest declares `powershell` as a Debian package dependency. Where that
  package comes from on a plain Debian system is not settled in this repository,
  and the ecosystem contract requires runtime dependencies to exist as Debian
  packages in stable. Resolving that is part of the packaging work, not
  something already solved.

## Installation

### From the package archive

Not available. The ecosystem APT repository is `hardensamba-apt`, and no
`samba-powershell` package has been built or published to it. When it exists,
installation will be:

```bash
sudo apt update
sudo apt install samba-powershell
```

Until then, that command fails with `Unable to locate package`.

### From source

This works today, and gets you the scaffold.

```bash
git clone https://github.com/HardenSamba/samba-powershell.git
cd samba-powershell

# Run it straight from the checkout, no installation
PYTHONPATH=src python3 -m samba_powershell.cli status
```

To build and install the Debian package from the checkout:

```bash
sudo apt install devscripts debhelper dh-python python3-all python3-setuptools
dpkg-buildpackage -us -uc -b
sudo apt install ../samba-powershell_0.1.0-1_all.deb
```

That path is written from `debian/control` and `debian/changelog`, which give
the package name and the `0.1.0-1` version in the filename. It is not exercised
anywhere: the CI workflow has no build job, and no package has been produced
from it yet. Treat it as the intended route rather than a tested one.

The ecosystem contract also expects an `install.sh` at the repository root, for
manual installation on a Debian or Ubuntu system without the archive. This
repository does not carry one yet.

## Usage

### What runs today

```console
$ PYTHONPATH=src python3 -m samba_powershell.cli status
samba-powershell: not implemented yet
```

That is the whole of it. The exit code is 0, which is deliberate: the command
succeeded at reporting that there is nothing to report.

```console
$ PYTHONPATH=src python3 -m samba_powershell.cli --help
usage: Import-Module [-h] [--version] {status} ...

PowerShell on Linux for Samba Active Directory administration.

positional arguments:
  {status}
    status    report what this module currently sees

options:
  -h, --help  show this help message and exit
  --version   show program's version number and exit
```

The `usage:` line reads `Import-Module` because `src/samba_powershell/cli.py`
passes `prog="Import-Module"` to the argument parser. `pyproject.toml` declares
the same string as its console script name, and `MODULE.yaml` declares the
command as `Import-Module SambaAD`. All three are scaffold artefacts.
`Import-Module` is a PowerShell keyword, not a shell command, and the naming
will be corrected when the real cmdlet surface lands.

### What is planned

**None of the following works. It is shown so the target is visible.**

```powershell
# Planned, not implemented
Import-Module SambaAD

Get-ADUser -Identity jdoe
Get-ADUser -Filter 'Name -like "j*"' -Properties mail,memberOf
Get-ADGroupMember -Identity 'Domain Admins' -Recursive

New-ADUser -Name 'Jane Doe' -SamAccountName jdoe -Path 'OU=Staff,DC=example,DC=com'
Set-ADUser -Identity jdoe -Department Engineering
Set-ADAccountPassword -Identity jdoe -Reset
Remove-ADUser -Identity jdoe -WhatIf
```

Authentication will follow the transport: Kerberos through the existing ticket
cache, with the directory enforcing the rights of the calling principal. The
module will not carry a permission model of its own.

## Configuration

Configuration lives in `/etc/hardensamba/samba-powershell/`, which is the
`writes.config_dir` declared in `MODULE.yaml`. Per the ecosystem contract, the
module owns that directory and must not write outside it.

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

[output]
# Attributes returned when a cmdlet is called without -Properties.
# Keeping this list short keeps queries against large directories cheap.
default_properties = distinguishedName,name,objectClass,sAMAccountName
```

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

python3 -m pytest tests -q        # 3 passed
mypy --strict src                 # Success: no issues found in 2 source files
```

`python3-yaml` and `python3-jsonschema` are there for `modulekit`, which needs
both and is not otherwise a dependency of this module.

Both contract checks must pass before a commit, and both pass today:

```bash
modulekit validate .              # the manifest and the write surface
modulekit lint src tests          # the coding standard, section 8
```

If `modulekit` is not installed, run it from a checkout:

```bash
git clone https://github.com/HardenSamba/hardensamba-modulekit /tmp/mk
PYTHONPATH=/tmp/mk/src python3 -m modulekit.cli validate .
PYTHONPATH=/tmp/mk/src python3 -m modulekit.cli lint src tests
```

CI runs on `debian:stable`, never on a HardenSamba image. A test that only
passes with extra software installed is a defect in the test.

What CI does not do is gate anything, so read `.github/workflows/ci.yml` before
trusting a green tick:

- The contract job runs `modulekit validate .`, but the clone that fetches
  `modulekit` ends in `|| true` and the check is wrapped in a directory test. A
  failed clone skips the check and the job still reports success.
- The test job runs `python3 -m pytest tests -q || echo "no tests yet"`, so a
  failing test does not fail the build.
- `modulekit lint` is never invoked in CI at all. The coding standard is checked
  only by whoever runs it locally.
- `python3-mypy` is installed in the test job and then never run.

Making those steps blocking is outstanding work, not something already in
place.

### Layout

| Path | Contents |
|---|---|
| `MODULE.yaml` | The manifest. Authoritative for dependencies and the write surface |
| `CLAUDE.md` | Project instructions, restating the parts of the contract that bind here |
| `src/samba_powershell/` | The Python package: `__init__.py` and `cli.py` |
| `tests/` | Smoke tests, runnable without the rest of the ecosystem |
| `docs/` | Documentation, English. Where `architecture.md` will land |
| `debian/` | Packaging. The reference installation method |
| `.github/workflows/` | CI on plain Debian: contract validation and pytest |
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
linter yet, so until it does, running it before a commit is on you.

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

**Not settled.** This repository carries no `LICENSE` file, and inventing one
here would be worse than saying so.

This is a greenfield module, not a fork. There is no upstream project, no
inherited licence and no divergence to describe. The closest reference points
are the published cmdlet surface of the Windows `ActiveDirectory` module and the
wire behaviour implemented in `samba-adws`, and neither is a code ancestor of
anything here.

A licence will be chosen and committed before the first release. Until a
`LICENSE` file exists, treat the terms as undetermined.
