"""Translation of samba-adws client failures into backend errors."""

from __future__ import annotations

from samba_powershell.errors import BackendError


# Preserves typed client fields while supplying safe boundary defaults.
def translate_client_error(error: Exception) -> BackendError:
    message_value: object = getattr(error, "message", str(error))
    code_value: object = getattr(error, "code", "ClientFailure")
    category_value: object = getattr(error, "category", "NotSpecified")
    target_value: object = getattr(error, "target", None)
    message = message_value if isinstance(message_value, str) else str(error)
    code = code_value if isinstance(code_value, str) else "ClientFailure"
    category = category_value if isinstance(category_value, str) else "NotSpecified"
    target = target_value if isinstance(target_value, str) else None
    error_id = code if code.startswith("SambaAD.") else f"SambaAD.{code}"
    return BackendError(message, error_id, category, target)
