from __future__ import annotations

from typing import Any

from . import modeler, process_cleanup, project_identity


def inspect(project_path: str = "") -> dict[str, Any]:
    return process_cleanup.inspect_cst_environment(project_path=project_path)


def open_project(project_path: str) -> dict[str, Any]:
    result = modeler.open_project(project_path)
    if result.get("status") == "error":
        return result
    return {
        **result,
        "session_action": "open",
        "post_inspect": inspect(project_path),
        "runtime_module": "cst_runtime.session_manager",
    }


def reattach_project(project_path: str) -> dict[str, Any]:
    status = project_identity.verify_project_identity(project_path)
    if status.get("status") == "error":
        return {
            **status,
            "session_action": "reattach",
            "post_inspect": inspect(project_path),
            "runtime_module": "cst_runtime.session_manager",
        }
    return {
        **status,
        "session_action": "reattach",
        "post_inspect": inspect(project_path),
        "runtime_module": "cst_runtime.session_manager",
    }


def close_project(
    project_path: str,
    save: bool = False,
    wait_unlock: bool = True,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.5,
) -> dict[str, Any]:
    close_result = modeler.close_project(project_path=project_path, save=save)
    unlock_result: dict[str, Any] | None = None
    if close_result.get("status") != "error" and wait_unlock:
        unlock_result = project_identity.wait_project_unlocked(
            project_path=project_path,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    status = "success"
    if close_result.get("status") == "error" or (unlock_result or {}).get("status") == "error":
        status = "error"
    payload: dict[str, Any] = {
        "status": status,
        "session_action": "close",
        "project_path": project_path,
        "save": save,
        "close_result": close_result,
        "unlock_result": unlock_result,
        "post_inspect": inspect(project_path),
        "runtime_module": "cst_runtime.session_manager",
    }
    if status == "error":
        payload["error_type"] = "session_close_failed"
        payload["message"] = "close_project or lock-release verification failed"
    return payload


def quit_cst(
    project_path: str = "",
    dry_run: bool = False,
    settle_seconds: float = 0.5,
) -> dict[str, Any]:
    before = inspect(project_path)
    cleanup = process_cleanup.cleanup_cst_processes(
        project_path=project_path,
        dry_run=dry_run,
        settle_seconds=settle_seconds,
    )
    after = inspect(project_path)
    status = "success" if cleanup.get("status") != "error" else "error"
    payload: dict[str, Any] = {
        "status": status,
        "session_action": "quit",
        "project_path": project_path,
        "dry_run": dry_run,
        "pre_inspect": before,
        "cleanup_result": cleanup,
        "post_inspect": after,
        "runtime_module": "cst_runtime.session_manager",
    }
    if status == "error":
        payload["error_type"] = "session_quit_failed"
        payload["message"] = "cleanup_cst_processes did not finish cleanly"
    return payload
