from __future__ import annotations

import json
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any

from . import project_identity, workspace
from .errors import error_response
from .project_identity import find_lock_files

def _load_allowlist() -> list[str]:
    """加载CST进程白名单配置，带错误处理和回退"""
    workspace_root, _, _ = workspace.resolve_workspace_root("")
    config_path = workspace_root / "cst_process_allowlist.json"
    default_allowlist = [
        "cstd",
        "CST DESIGN ENVIRONMENT_AMD64",
        "CSTDCMainController_AMD64",
        "CSTDCSolverServer_AMD64",
    ]
    
    if not config_path.exists():
        return default_allowlist
    
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
            allowlist = config.get("cst_force_kill_process_allowlist", [])
            if not allowlist:
                warnings.warn(
                    f"Empty allowlist in {config_path}, using default",
                    UserWarning
                )
                return default_allowlist
            return allowlist
    except Exception as exc:
        warnings.warn(
            f"Failed to load allowlist from {config_path}: {exc}, using default",
            UserWarning
        )
        return default_allowlist

CST_FORCE_KILL_PROCESS_ALLOWLIST = _load_allowlist()


def _run_powershell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _loads_json_array(text: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return []
    value = json.loads(stripped)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _discover_cst_processes() -> list[dict[str, Any]]:
    names = ",".join(json.dumps(name) for name in CST_FORCE_KILL_PROCESS_ALLOWLIST)
    command = f"""
$allow = @({names})
$items = @()
foreach ($name in $allow) {{
  $items += Get-Process -Name $name -ErrorAction SilentlyContinue |
    ForEach-Object {{
      [pscustomobject]@{{
        pid = $_.Id
        name = $_.ProcessName
        main_window_title = $_.MainWindowTitle
      }}
    }}
}}
$items | Sort-Object pid -Unique | ConvertTo-Json -Depth 4
"""
    result = _run_powershell(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Get-Process failed")
    return _loads_json_array(result.stdout)


def _stop_process(pid: int, name: str) -> dict[str, Any]:
    command = f"""
try {{
  Stop-Process -Id {int(pid)} -Force -ErrorAction Stop
  [pscustomobject]@{{ status = "killed"; pid = {int(pid)}; name = {json.dumps(name)} }} | ConvertTo-Json -Depth 4
}} catch {{
  [pscustomobject]@{{
    status = "failed"
    pid = {int(pid)}
    name = {json.dumps(name)}
    error = $_.Exception.Message
  }} | ConvertTo-Json -Depth 4
}}
"""
    result = _run_powershell(command)
    if result.returncode != 0:
        return {
            "status": "failed",
            "pid": pid,
            "name": name,
            "error": result.stderr.strip() or result.stdout.strip() or "Stop-Process failed",
        }
    payload = json.loads(result.stdout.strip())
    if isinstance(payload, dict):
        return payload
    return {"status": "failed", "pid": pid, "name": name, "error": "unexpected Stop-Process output"}


def _is_access_denied(message: str) -> bool:
    lowered = message.lower()
    return "access is denied" in lowered or "拒绝访问" in lowered or "存取被拒" in lowered


def _lock_file_payload(paths: list[Path]) -> list[str]:
    return [path.as_posix() for path in paths]


def _inspect_next_steps(
    project_path: str,
    processes: list[dict[str, Any]],
    lock_files: list[Path],
    open_projects: dict[str, Any],
    identity_status: dict[str, Any] | None,
) -> list[str]:
    steps: list[str] = []
    if not project_path:
        steps.append("Pass project_path to include lock-file and project-identity checks.")
    if (identity_status or {}).get("error_type") == "ambiguous_open_projects":
        steps.append("Close unrelated CST projects before writing or attaching to a project.")
    if (identity_status or {}).get("error_type") == "project_not_open" and (identity_status or {}).get("open_projects"):
        steps.append("Do not attach to the wrong open project; close or switch CST to the expected project.")
    if lock_files:
        steps.append("Close the matching CST project, then run wait-project-unlocked before copying or reopening.")
    if processes:
        steps.append("If the project is closed and locks are clear, run cleanup-cst-processes and record any Access is denied residuals.")
    if open_projects.get("error_type") == "no_cst_session" and not processes and not lock_files:
        steps.append("No CST session is visible and no allowlisted process or lock file was found.")
    if not steps:
        steps.append("Environment is clear for project copy or fresh-session reopen.")
    return steps


def inspect_cst_environment(project_path: str = "") -> dict[str, Any]:
    try:
        processes = _discover_cst_processes()
        lock_files: list[Path] = find_lock_files(project_path) if project_path else []
        open_projects = project_identity.list_open_projects()
        identity_status: dict[str, Any] | None = None
        if project_path:
            identity_status = project_identity.verify_project_identity(project_path)

        session_error = open_projects.get("status") == "error"
        identity_error_type = (identity_status or {}).get("error_type")
        identity_blocked = identity_error_type in {
            "ambiguous_open_projects",
            "no_active_project",
            "attach_active_project_failed",
            "list_open_projects_failed",
        }
        wrong_project_open = identity_error_type == "project_not_open" and bool(
            (identity_status or {}).get("open_projects")
        )
        process_count = len(processes)
        lock_count = len(lock_files)
        safe_to_copy_or_reopen = bool(project_path) and lock_count == 0 and not identity_blocked and not wrong_project_open
        cleanup_required = process_count > 0 or lock_count > 0

        readiness = "clear"
        if lock_count or identity_blocked or wrong_project_open:
            readiness = "blocked"
        elif process_count or session_error:
            readiness = "attention_required"

        return {
            "status": "success",
            "readiness": readiness,
            "project_path": str(project_path or ""),
            "force_kill_allowlist": CST_FORCE_KILL_PROCESS_ALLOWLIST,
            "processes": processes,
            "process_count": process_count,
            "lock_files": _lock_file_payload(lock_files),
            "lock_count": lock_count,
            "open_projects_status": open_projects,
            "project_identity_status": identity_status,
            "cleanup_required": cleanup_required,
            "safe_to_copy_or_reopen": safe_to_copy_or_reopen,
            "next_steps": _inspect_next_steps(
                project_path=project_path,
                processes=processes,
                lock_files=lock_files,
                open_projects=open_projects,
                identity_status=identity_status,
            ),
            "runtime_module": "cst_runtime.process_cleanup",
        }
    except Exception as exc:
        return error_response(
            "inspect_cst_environment_failed",
            f"inspect_cst_environment failed: {str(exc)}",
            force_kill_allowlist=CST_FORCE_KILL_PROCESS_ALLOWLIST,
            project_path=str(project_path or ""),
            runtime_module="cst_runtime.process_cleanup",
        )


def cleanup_cst_processes(
    project_path: str = "",
    dry_run: bool = False,
    settle_seconds: float = 0.5,
) -> dict[str, Any]:
    try:
        before = _discover_cst_processes()
        lock_files_before: list[Path] = find_lock_files(project_path) if project_path else []

        attempts: list[dict[str, Any]] = []
        if not dry_run:
            for proc in before:
                attempts.append(_stop_process(int(proc["pid"]), str(proc["name"])))
            time.sleep(max(0.0, float(settle_seconds)))

        after = _discover_cst_processes()
        lock_files_after: list[Path] = find_lock_files(project_path) if project_path else []
        
        # Access is denied的进程直接忽略，不标记为残留
        access_denied = [
            item
            for item in attempts
            if item.get("status") == "failed" and _is_access_denied(str(item.get("error", "")))
        ]
        other_failures = [
            item
            for item in attempts
            if item.get("status") == "failed" and item not in access_denied
        ]
        
        # 过滤掉Access is denied的进程，它们被忽略不计
        if after:
            after = [
                proc for proc in after 
                if not any(
                    item.get("pid") == proc.get("pid") 
                    and _is_access_denied(str(item.get("error", "")))
                    for item in access_denied
                )
            ]

        cleanup_status = "dry_run" if dry_run else "completed"
        message = "CST process cleanup completed"
        if dry_run:
            message = "CST process cleanup dry run completed"
        elif after or other_failures or lock_files_after:
            return error_response(
                "cleanup_cst_processes_blocked",
                "CST process cleanup did not finish cleanly",
                cleanup_status="blocked",
                force_kill_allowlist=CST_FORCE_KILL_PROCESS_ALLOWLIST,
                project_path=str(project_path or ""),
                lock_files_before=_lock_file_payload(lock_files_before),
                lock_files_after=_lock_file_payload(lock_files_after),
                processes_before=before,
                attempts=attempts,
                processes_after=after,
                access_denied=access_denied,
                other_failures=other_failures,
                runtime_module="cst_runtime.process_cleanup",
            )

        return {
            "status": "success",
            "cleanup_status": cleanup_status,
            "message": message,
            "force_kill_allowlist": CST_FORCE_KILL_PROCESS_ALLOWLIST,
            "project_path": str(project_path or ""),
            "lock_files_before": _lock_file_payload(lock_files_before),
            "lock_files_after": _lock_file_payload(lock_files_after),
            "processes_before": before,
            "attempts": attempts,
            "processes_after": after,
            "access_denied": access_denied,
            "runtime_module": "cst_runtime.process_cleanup",
        }
    except Exception as exc:
        return error_response(
            "cleanup_cst_processes_failed",
            f"cleanup_cst_processes failed: {str(exc)}",
            force_kill_allowlist=CST_FORCE_KILL_PROCESS_ALLOWLIST,
            project_path=str(project_path or ""),
            runtime_module="cst_runtime.process_cleanup",
        )
