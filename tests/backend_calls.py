"""Building backend requests and dispatching them against the offline fake."""

from __future__ import annotations

import pytest

from samba_powershell.dispatcher import dispatch
from samba_powershell.errors import BackendError
from tests.fake_client import FakeClient


# Builds a valid request for one operation against the recorded directory.
def request_for(operation: str, identity: str,
                properties: list[str] | None = None) -> dict[str, object]:
    return {
        "version": 1,
        "operation": operation,
        "parameters": {
            "identity": identity,
            "server": "dc1.example.com",
            "properties": properties or [],
        },
    }


# Dispatches one request and returns the rendered properties and the client.
def answered(request: dict[str, object]) -> tuple[dict[str, object], FakeClient]:
    made: list[FakeClient] = []

    # Builds the fake while keeping hold of it, so the test can read what the
    # backend actually asked the client for.
    def factory(server: str, port: int, timeout: float) -> FakeClient:
        made.append(FakeClient(server, port, timeout))
        return made[-1]

    result = dispatch(request, factory)
    assert isinstance(result, dict)
    properties = result["properties"]
    assert isinstance(properties, dict)
    return properties, made[0]


# Dispatches one request that must fail, and returns the error it raised.
def refused(request: dict[str, object]) -> BackendError:
    with pytest.raises(BackendError) as raised:
        dispatch(request, FakeClient)
    return raised.value
