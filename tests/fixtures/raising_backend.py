#!/usr/bin/env python3
"""A backend fixture that must never be reached: it fails on any invocation.

The PowerShell write test points -WhatIf runs at this. A -WhatIf run that
succeeds proves the cmdlet short-circuited before starting the backend, because
if it had started, this would have refused.
"""

from __future__ import annotations

import json
import sys

sys.stdin.read()
sys.stdout.write(json.dumps({
    "version": 1, "ok": False,
    "error": {"message": "The backend was reached when it should not have been.",
              "error_id": "SambaAD.BackendReached", "category": "NotSpecified",
              "target": None},
}, separators=(",", ":")) + "\n")
raise SystemExit(1)
