"""Stub of ldap.controls: the paged results control the backend sends."""

from __future__ import annotations


# Holds a control's value, as the real control does.
class RequestControl:
    # Stores the control as given.
    def __init__(self, controlType: str, criticality: bool = False,
                 encodedControlValue: bytes = b"") -> None:
        self.controlType = controlType
        self.criticality = criticality
        self.encodedControlValue = encodedControlValue


# Holds what one page asks for, as the real control does.
class SimplePagedResultsControl:
    controlType = "1.2.840.113556.1.4.319"

    # Stores the page size and the cookie.
    def __init__(self, criticality: bool = False, size: int = 10, cookie: bytes = b"") -> None:
        self.criticality = criticality
        self.size = size
        self.cookie = cookie
