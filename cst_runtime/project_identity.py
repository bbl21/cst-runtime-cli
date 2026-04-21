from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .errors import error_response


def normalize_project_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.expanduser(path)))


def project_path_from_args(args: dict[str, Any]) -> str:
    project_path = args.get("project_path") or args.get("fullpath") or args.get("working_project")
    if not project_path:
        raise ValueError("project_path is required")
    return str(project_path)


def infer_run_dir_from_project(project_path: str) -> Path | None:
    path = Path(project_path).expanduser().resolve()
    if path.parent.name.lower() == "projects":
        return path.parent.parent
    return None


def _project_companion_dir(project_path: str) -> Path:
    path = Path(project_path).expanduser().resolve()
    if path.suffix.lower() != ".cst":
        path = path.with_suffix(".cst")
    return path.with_suffix("")


def find_lock_files(project_path: str) -> list[Path]:
    companion_dir = _project_companion_dir(project_path)
    if not companion_dir.exists():
        return []
    return sorted(companion_dir.rglob("*.lok"))


def wait_project_unlocked(
    project_path: str,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.5,
) -> dict[str, Any]:
    started = time.monotonic()
    last_locks: list[Path] = []
    while True:
        last_locks = find_lock_files(project_path)
        if not last_locks:
            return {
                "status": "success",
                "project_path": os.path.abspath(project_path),
                "locked": False,
                "waited_seconds": round(time.monotonic() - started, 3),
                "runtime_module": "cst_runtime.project_identity",
            }
        if time.monotonic() - started >= timeout_seconds:
            return error_response(
                "lock_not_released",
                "project lock files still exist after timeout",
                project_path=os.path.abspath(project_path),
                locked=True,
                lock_files=[path.as_posix() for path in last_locks],
                timeout_seconds=timeout_seconds,
                runtime_module="cst_runtime.project_identity",
            )
        time.sleep(poll_interval_seconds)


def _connect_to_any():
    try:
        import cst.interface

        return cst.interface.DesignEnvironment.connect_to_any()
    except Exception as exc:
        return None, str(exc)


def list_open_projects() -> dict[str, Any]:
    connected = _connect_to_any()
    if isinstance(connected, tuple):
        return error_response(
            "no_cst_session",
            connected[1],
            open_projects=[],
            runtime_module="cst_runtime.project_identity",
        )
    de = connected
    try:
        paths = [str(path) for path in list(de.list_open_projects() or [])]
    except Exception as exc:
        return error_response(
            "list_open_projects_failed",
            str(exc),
            open_projects=[],
            runtime_module="cst_runtime.project_identity",
        )
    return {
        "status": "success",
        "open_projects": [
            {
                "project_path": os.path.abspath(path),
                "project_name": Path(path).stem,
            }
            for path in paths
        ],
        "count": len(paths),
        "runtime_module": "cst_runtime.project_identity",
    }


def attach_expected_project(project_path: str) -> tuple[Any | None, dict[str, Any]]:
    expected = normalize_project_path(project_path)
    connected = _connect_to_any()
    if isinstance(connected, tuple):
        return None, error_response(
            "no_cst_session",
            connected[1],
            expected_project_path=os.path.abspath(project_path),
            runtime_module="cst_runtime.project_identity",
        )

    de = connected
    try:
        open_projects = list(de.list_open_projects() or [])
    except Exception as exc:
        return None, error_response(
            "list_open_projects_failed",
            str(exc),
            expected_project_path=os.path.abspath(project_path),
            runtime_module="cst_runtime.project_identity",
        )

    normalized_open = [normalize_project_path(str(path)) for path in open_projects]
    matching = [
        str(path)
        for path, normalized in zip(open_projects, normalized_open)
        if normalized == expected
    ]
    if not matching:
        return None, error_response(
            "project_not_open",
            "expected project is not open in CST",
            expected_project_path=os.path.abspath(project_path),
            open_projects=[str(path) for path in open_projects],
            runtime_module="cst_runtime.project_identity",
        )

    if len(open_projects) != 1:
        return None, error_response(
            "ambiguous_open_projects",
            "Refusing to attach because multiple CST projects are open.",
            expected_project_path=os.path.abspath(project_path),
            open_projects=[str(path) for path in open_projects],
            runtime_module="cst_runtime.project_identity",
        )

    try:
        if not de.has_active_project():
            return None, error_response(
                "no_active_project",
                "CST session has no active project",
                expected_project_path=os.path.abspath(project_path),
                open_projects=[str(path) for path in open_projects],
                runtime_module="cst_runtime.project_identity",
            )
        return de.active_project(), {
            "status": "success",
            "expected_project_path": os.path.abspath(project_path),
            "open_projects": [str(path) for path in open_projects],
            "runtime_module": "cst_runtime.project_identity",
        }
    except Exception as exc:
        return None, error_response(
            "attach_active_project_failed",
            str(exc),
            expected_project_path=os.path.abspath(project_path),
            open_projects=[str(path) for path in open_projects],
            runtime_module="cst_runtime.project_identity",
        )


def verify_project_identity(project_path: str) -> dict[str, Any]:
    _, status = attach_expected_project(project_path)
    return status

