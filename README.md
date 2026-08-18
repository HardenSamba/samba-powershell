# samba-powershell

> PowerShell on Linux for Samba Active Directory administration.

## Status

Early development. Not ready for production use.

## What it does

Provides the Active Directory cmdlets on Linux, so a domain can be administered from a terminal without a Windows workstation.

## Why it exists

Administrators already know these cmdlets. Nothing open source provides them outside Windows, which forces a Windows machine into every administration workflow.

## In scope

- A PowerShell module exposing the familiar cmdlet surface
- A Python backend carrying the logic
- Shell integration and tab completion

## Out of scope

- Reimplementing the wire protocol, which belongs to `samba-adws`

## Requirements

- A running Samba AD domain
- `samba-adws` (depends): The cmdlets speak the web services protocol.
- Debian packages: `powershell`

This module installs on: domain-controller, workstation.

## Contract

This module follows the [HardenSamba module contract](https://github.com/HardenSamba/hardensamba-modulekit). Run `modulekit validate .` before opening a pull request.
