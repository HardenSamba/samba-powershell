"""Tests for the versioned JSON process boundary."""

from __future__ import annotations

from io import StringIO

import pytest

from samba_powershell.errors import BackendError
from samba_powershell.protocol import (
    failure_response,
    read_request,
    success_response,
    validate_request,
    write_response,
)


# A complete request survives parsing and validation.
def test_valid_request_round_trip() -> None:
    source = StringIO('{"version":1,"operation":"get_ad_user","parameters":{}}')
    request = validate_request(read_request(source))
    assert request["operation"] == "get_ad_user"


# Protocol mismatches carry a stable error identifier.
def test_protocol_version_is_rejected() -> None:
    request = {"version": 2, "operation": "get_ad_user", "parameters": {}}
    with pytest.raises(BackendError) as raised:
        validate_request(request)
    assert raised.value.error_id == "SambaAD.ProtocolMismatch"


# Success output is one compact Unicode-safe JSON line.
def test_success_response_is_one_line() -> None:
    output = StringIO()
    write_response(success_response({"name": "René"}), output)
    assert output.getvalue() == '{"version":1,"ok":true,"result":{"name":"René"}}\n'


# Error output preserves every field PowerShell needs for ErrorRecord.
def test_error_response_preserves_fields() -> None:
    error = BackendError("missing", "SambaAD.NotFound", "ObjectNotFound", "alice")
    response = failure_response(error)
    assert response["error"] == {
        "message": "missing",
        "error_id": "SambaAD.NotFound",
        "category": "ObjectNotFound",
        "target": "alice",
    }
