#!/usr/bin/env python3
"""Echo backends used only by the process transport benchmark."""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path


# Echoes one argument request for the isolated-process prototype.
def echo_once(request: str) -> int:
    print(request)
    return 0


# Exchanges sequential lines until the benchmark sends its stop marker.
def echo_connection(connection: socket.socket) -> None:
    stream = connection.makefile("rwb", buffering=0)
    request = stream.readline()
    while request and request != b"__quit__\n":
        stream.write(request)
        request = stream.readline()
    stream.close()


# Hosts the resident-process prototype on one Unix-domain socket.
def serve(socket_path: Path) -> int:
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)
    connection, _ = listener.accept()
    echo_connection(connection)
    connection.close()
    listener.close()
    return 0


# Selects the isolated or resident echo backend.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("once", "serve"))
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()
    if args.mode == "once":
        if args.value is None:
            parser.error("once requires a JSON request argument")
        return echo_once(args.value)
    if args.value is None:
        parser.error("serve requires a socket path")
    return serve(Path(args.value))


if __name__ == "__main__":
    raise SystemExit(main())
