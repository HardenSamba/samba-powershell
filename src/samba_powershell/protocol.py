"""Versioned JSON envelopes shared by PowerShell and Python."""

from __future__ import annotations

import json
from typing import TextIO, cast

from samba_powershell.errors import BackendError

PROTOCOL_VERSION = 1


# Reads one request object from standard input.
def read_request(stream: TextIO) -> dict[str, object]:
    try:
        value: object = json.load(stream)
    except json.JSONDecodeError as exc:
        raise BackendError(
            "The backend request is not valid JSON.",
            "SambaAD.InvalidRequest",
            "ParserError",
        ) from exc
    if not isinstance(value, dict):
        raise BackendError(
            "The backend request must be a JSON object.",
            "SambaAD.InvalidRequest",
            "ParserError",
        )
    return cast(dict[str, object], value)


# Validates the stable fields before an operation sees the request.
def validate_request(request: dict[str, object]) -> dict[str, object]:
    version = request.get("version")
    operation = request.get("operation")
    parameters = request.get("parameters")
    if version != PROTOCOL_VERSION:
        raise BackendError(
            f"Unsupported backend protocol version: {version!r}.",
            "SambaAD.ProtocolMismatch",
            "InvalidData",
        )
    if not isinstance(operation, str) or not isinstance(parameters, dict):
        raise BackendError(
            "The request needs an operation string and a parameters object.",
            "SambaAD.InvalidRequest",
            "ParserError",
        )
    return request


# Builds a successful response envelope.
def success_response(result: object) -> dict[str, object]:
    return {"version": PROTOCOL_VERSION, "ok": True, "result": result}


# Builds a failed response envelope from a typed backend error.
def failure_response(error: BackendError) -> dict[str, object]:
    return {"version": PROTOCOL_VERSION, "ok": False, "error": error.as_payload()}


# Writes exactly one compact JSON response to standard output.
def write_response(response: dict[str, object], stream: TextIO) -> None:
    encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
    stream.write(f"{encoded}\n")
