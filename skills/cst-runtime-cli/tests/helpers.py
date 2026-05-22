"""Shared test factory functions for cst-runtime-cli tests."""
from pathlib import Path
import json


def make_s11_json(path: Path, run_id: int, xdata: list, pairs: list) -> Path:
    """Create a valid S11 export JSON file.

    pairs: list of [real, imag] e.g. [[0.3, 0.0], [0.1, 0.0]]
    """
    ydata = [{"real": r, "imag": i} for r, i in pairs]
    data = {"run_id": run_id, "xdata": xdata, "ydata": ydata}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def assert_json_success(result: dict) -> dict:
    """Assert JSON response status is success."""
    assert result["status"] == "success", f"Expected success, got: {result}"
    return result


def assert_json_error(result: dict, error_type: str) -> dict:
    """Assert JSON response has specific error type."""
    assert result["status"] == "error", f"Expected error, got: {result}"
    assert result["error_type"] == error_type, \
        f"Expected error_type='{error_type}', got: '{result.get('error_type')}'"
    return result
