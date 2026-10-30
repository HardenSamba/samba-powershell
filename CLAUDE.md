# samba-powershell: project instructions

## 1. What this repository is

Provides the Active Directory cmdlets on Linux, so a domain can be administered from a terminal without a Windows workstation.

It is one module of the HardenSamba ecosystem. It installs and runs on a plain
Debian system; it must never require the HardenSamba image.

## 2. Read first

1. The [module contract](https://github.com/HardenSamba/hardensamba-modulekit)
   is normative. Everything below only restates parts of it.
2. `MODULE.yaml` declares what this module needs and what it touches. Anything
   not declared there must not be written.

## 3. Boundaries

In scope:
- A PowerShell module exposing the familiar cmdlet surface
- A Python backend carrying the logic
- Shell integration and tab completion

Out of scope:
- Reimplementing LDAP, SASL or Kerberos, which come from `python3-ldap` and the
  system libraries

Declared module dependencies: none. The module talks to the directory over LDAP
and needs nothing on a domain controller but Samba itself.

## 4. Non-negotiable rules

- Python 3.11 or later. Runtime dependencies must exist as Debian packages in
  stable; never invoke `pip` at install or run time.
- `python3-samba` is not thread-safe. Use processes, not threads, and never
  open a directory handle at import time.
- Do not invent Active Directory attributes, classes or object identifiers. A
  Windows controller refuses to replicate with a divergent schema.
- Everything in English: code, identifiers, comments, documentation, commits.
  Verbatim client error messages keep their original language.
- Ground protocol work in the published specifications. Never derive from
  disassembled or otherwise obscure sources, and never mirror the internal
  naming of a proprietary implementation.

<!-- modulekit: allow-provenance-marker -->

## 5. Quality gates

- `modulekit validate .` must pass.
- `mypy --strict` and `pytest` must pass.
- Tests run on plain Debian in CI, never on a HardenSamba image.

## 6. Deliverables

- Debian packaging under `debian/`, producing an installable package.
- A manual installation path for a Debian system without the package archive.
- Documentation in `docs/`, kept current with every behaviour change.
