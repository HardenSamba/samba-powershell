#!/usr/bin/env python3
"""Deterministic process fixture for the PowerShell boundary test."""

from __future__ import annotations

import json
import sys
from typing import cast

# Envelopes that are JSON and version 1 but miss what the cmdlets read, keyed
# by the identity that asks for them, with the exit code each comes with.
MALFORMED: dict[str, tuple[str, int]] = {
    "noresult": ('{"version":1,"ok":true}', 0),
    "noerror": ('{"version":1,"ok":false}', 1),
    "casedupe": ('{"version":1,"ok":true,"result":{"type":"SambaAD.User","properties":'
                 '{"DistinguishedName":"a","distinguishedname":"b"}}}', 0),
}

request = cast(dict[str, object], json.load(sys.stdin))
parameters = cast(dict[str, object], request["parameters"])
identity = cast(str, parameters["identity"])
if identity == "garbage":
    sys.stdout.write("this is not the protocol\n")
    sys.stderr.write("Traceback (most recent call last): a fake crash\n")
    raise SystemExit(1)
if identity in MALFORMED:
    text, code = MALFORMED[identity]
    sys.stdout.write(text + "\n")
    raise SystemExit(code)
if identity == "missing":
    response: dict[str, object] = {
        "version": 1,
        "ok": False,
        "error": {
            "message": "The directory object was not found.",
            "error_id": "SambaAD.IdentityNotFound",
            "category": "ObjectNotFound",
            "target": identity,
        },
    }
else:
    response = {
        "version": 1,
        "ok": True,
        "result": {
            "type": "SambaAD.User",
            "properties": {
                "DistinguishedName": identity,
                "info": "2026-01-01T10:00:00+00:00",
                "Name": "Alice",
                "SamAccountName": "alice",
                "Surname": None,
                "whenCreated": "2024-02-29T12:00:00+00:00",
            },
            "datetimes": ["whenCreated"],
        },
    }
json.dump(response, sys.stdout, separators=(",", ":"))
sys.stdout.write("\n")
raise SystemExit(0 if response["ok"] is True else 1)
