"""Backend errors that cross the PowerShell process boundary."""

from __future__ import annotations


# Describes an actionable backend failure without exposing a Python traceback.
class BackendError(Exception):
    # Stores the fields PowerShell needs to construct an ErrorRecord.
    def __init__(
        self,
        message: str,
        error_id: str,
        category: str = "NotSpecified",
        target: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_id = error_id
        self.category = category
        self.target = target

    # Serialises the public error fields for the JSON response envelope.
    def as_payload(self) -> dict[str, object]:
        return {
            "message": self.message,
            "error_id": self.error_id,
            "category": self.category,
            "target": self.target,
        }
