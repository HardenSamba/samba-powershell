"""Command line entry point for the PowerShell backend."""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from samba_powershell import __version__
from samba_powershell.dispatcher import dispatch
from samba_powershell.errors import BackendError
from samba_powershell.protocol import (
    failure_response,
    read_request,
    success_response,
    validate_request,
    write_response,
)


# Builds the backend command-line parser.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="samba-ad-backend",
        description="PowerShell backend for Samba Active Directory administration.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("request", help="read one JSON request from standard input")
    sub.add_parser("status", help="report whether the backend can start")
    return parser


# Parses arguments and dispatches to a subcommand.
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "request":
        return request(sys.stdin, sys.stdout)
    if args.command == "status":
        return status()
    return 1


# Handles one request without allowing exceptions onto the JSON channel.
def request(input_stream: TextIO, output_stream: TextIO) -> int:
    try:
        payload = success_response(dispatch(validate_request(read_request(input_stream))))
        write_response(payload, output_stream)
    except BackendError as exc:
        write_response(failure_response(exc), output_stream)
        return 1
    except Exception:
        write_response(
            failure_response(
                BackendError("The backend failed.", "SambaAD.BackendFailure")
            ),
            output_stream,
        )
        return 1
    return 0


# Reports that the local backend process can start.
def status() -> int:
    print("samba-ad-backend: ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
