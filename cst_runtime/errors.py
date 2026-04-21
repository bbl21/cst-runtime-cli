from __future__ import annotations

from typing import Any


def error_response(
    error_type: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "error",
        "error_type": error_type,
        "message": message,
    }
    payload.update(extra)
    return payload


def success_response(**payload: Any) -> dict[str, Any]:
    return {"status": "success", **payload}

