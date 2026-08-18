"""Command line entry point."""

from __future__ import annotations

import argparse
import sys

from samba_powershell import __version__


# Parses arguments and dispatches to a subcommand.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="Import-Module", description="PowerShell on Linux for Samba Active Directory administration.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="report what this module currently sees")
    args = parser.parse_args(argv)
    if args.command == "status":
        return status()
    return 1


# Reports the module state. Replaced as the module grows.
def status() -> int:
    print("samba-powershell: not implemented yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
