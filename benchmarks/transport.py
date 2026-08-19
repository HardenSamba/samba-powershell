#!/usr/bin/env python3
"""Measures the two process transports required by architecture ticket 2."""

from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PAYLOAD = b'{"version":1,"operation":"ping","parameters":{}}\n'
BACKEND = Path(__file__).with_name("echo_backend.py")


# Measures isolated interpreter startup for one call and repeated calls.
def measure_process(iterations: int) -> dict[str, float | int]:
    request = PAYLOAD.decode("utf-8").rstrip("\n")
    command = [sys.executable, str(BACKEND), "once", request]
    started = time.perf_counter_ns()
    subprocess.run(command, check=True, capture_output=True)
    cold = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    for _ in range(iterations):
        subprocess.run(command, check=True, capture_output=True)
    repeated = time.perf_counter_ns() - started
    return {
        "cold_one_ms": cold / 1e6,
        "sequential_ms": repeated / 1e6,
        "iterations": iterations,
    }


# Connects once the resident process has bound its Unix-domain socket.
def connect_client(
    socket_path: Path,
    process: subprocess.Popen[bytes],
) -> socket.socket:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            client.connect(str(socket_path))
            return client
        except OSError:
            time.sleep(0.001)
    process.kill()
    client.close()
    raise TimeoutError("The Unix-domain socket did not become ready.")


# Measures the first and repeated exchanges on one connected socket.
def exchange(
    client: socket.socket,
    started: int,
    iterations: int,
) -> tuple[int, int]:
    stream = client.makefile("rwb", buffering=0)
    stream.write(PAYLOAD)
    stream.readline()
    cold = time.perf_counter_ns() - started
    started = time.perf_counter_ns()
    for _ in range(iterations):
        stream.write(PAYLOAD)
        stream.readline()
    repeated = time.perf_counter_ns() - started
    stream.write(b"__quit__\n")
    stream.close()
    return cold, repeated


# Measures startup and warm requests through the resident socket prototype.
def measure_socket(socket_path: Path, iterations: int) -> dict[str, float | int]:
    command = [sys.executable, str(BACKEND), "serve", str(socket_path)]
    started = time.perf_counter_ns()
    process = subprocess.Popen(command)
    client = connect_client(socket_path, process)
    cold, repeated = exchange(client, started, iterations)
    client.close()
    process.wait(timeout=5)
    return {
        "cold_one_ms": cold / 1e6,
        "sequential_ms": repeated / 1e6,
        "iterations": iterations,
    }


# Runs both prototypes and prints their comparable measurements as JSON.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    iterations = parser.parse_args().iterations
    process_result = measure_process(iterations)
    with tempfile.TemporaryDirectory(prefix="samba-ad-benchmark-") as directory:
        if hasattr(socket, "AF_UNIX"):
            path = Path(directory) / "backend.sock"
            socket_result: object = measure_socket(path, iterations)
        else:
            socket_result = {"skipped": "AF_UNIX is unavailable on this host."}
    result = {"process": process_result, "unix_socket": socket_result}
    result["platform"] = {"python": sys.version.split()[0], "os": platform.system()}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
