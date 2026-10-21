#!/usr/bin/env python3
"""Deterministic process fixture for the PowerShell boundary test."""

from __future__ import annotations

import json
import sys
from typing import cast

# Envelopes that are JSON and version 1 but miss what the cmdlets read, keyed
# by the identity that asks for them, with the exit code each comes with.
VALID_RESULT = '"result":{"type":"SambaAD.User","properties":{"DistinguishedName":"a"}}'
MALFORMED: dict[str, tuple[str, int]] = {
    "noresult": ('{"version":1,"ok":true}', 0),
    "noerror": ('{"version":1,"ok":false}', 1),
    "casedupe": ('{"version":1,"ok":true,"result":{"type":"SambaAD.User","properties":'
                 '{"DistinguishedName":"a","distinguishedname":"b"}}}', 0),
    "envdupe": ('{"version":1,"ok":true,"OK":true,' + VALID_RESULT + '}', 0),
    "emptykey": ('{"version":1,"ok":true,"result":{"type":"SambaAD.User","properties":'
                 '{"DistinguishedName":"a","":1}}}', 0),
    "deep": ('{"version":1,"ok":true,"result":{"type":"SambaAD.User","properties":'
             '{"DistinguishedName":"a","x":[[[[[[[[[[1]]]]]]]]]]}}}', 0),
    "dtnull": ('{"version":1,"ok":true,"result":{"type":"SambaAD.User","properties":'
               '{"DistinguishedName":"a"},"datetimes":null}}', 0),
    "typeempty": ('{"version":1,"ok":true,"result":{"type":"","properties":'
                  '{"DistinguishedName":"a"}}}', 0),
    "nodn": ('{"version":1,"ok":true,"result":{"type":"SambaAD.User","properties":{}}}', 0),
    "stringversion": ('{"version":"1","ok":true,' + VALID_RESULT + '}', 0),
    "numcategory": ('{"version":1,"ok":false,"error":{"message":"2026-01-01T10:00:00Z",'
                    '"error_id":"SambaAD.Fake","category":"13"}}', 1),
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
            "message": "Cannot find an object with identity 'missing'.",
            "error_id": "SambaAD.ObjectNotFound",
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
