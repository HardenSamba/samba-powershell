#!/usr/bin/env python3
"""Deterministic process fixture for the PowerShell boundary test."""

from __future__ import annotations

import json
import sys
from typing import cast

request = cast(dict[str, object], json.load(sys.stdin))
parameters = cast(dict[str, object], request["parameters"])
identity = cast(str, parameters["identity"])
if identity == "garbage":
    sys.stdout.write("this is not the protocol\n")
    sys.stderr.write("Traceback (most recent call last): a fake crash\n")
    raise SystemExit(1)
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
                "Name": "Alice",
                "SamAccountName": "alice",
                "Surname": None,
            },
        },
    }
json.dump(response, sys.stdout, separators=(",", ":"))
sys.stdout.write("\n")
raise SystemExit(0 if response["ok"] is True else 1)
