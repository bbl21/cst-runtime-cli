from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import error_response

WORKSPACE_META_DIR = ".cst_mcp_runtime"
WORKSPACE_META_FILE = "workspace.json"
WORKSPACE_SCHEMA_VERSION = 1


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def scripts_root() -> Path:
    return Path(__file__).resolve().parents[1]


def marker_path(workspace_root: Path) -> Path:
    return workspace_root / WORKSPACE_META_DIR / WORKSPACE_META_FILE


def find_workspace_marker(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        marker = marker_path(candidate)
        if marker.exists() and marker.is_file():
            return marker
    return None


def resolve_workspace_root(explicit_workspace: str = "") -> tuple[Path, str, bool]:
    if explicit_workspace:
        root = Path(explicit_workspace).expanduser().resolve()
        return root, "argument", marker_path(root).exists()

    env_workspace = os.environ.get("CST_MCP_WORKSPACE", "").strip()
    if env_workspace:
        root = Path(env_workspace).expanduser().resolve()
        return root, "CST_MCP_WORKSPACE", marker_path(root).exists()

    marker = find_workspace_marker()
    if marker:
        return marker.parents[1], "ancestor_marker", True

    return Path.cwd().resolve(), "cwd", False


def workspace_status(explicit_workspace: str = "") -> dict[str, Any]:
    root, source, initialized = resolve_workspace_root(explicit_workspace)
    marker = marker_path(root)
    expected_dirs = ["tasks", "refs", "docs"]
    return {
        "workspace_root": root.as_posix(),
        "workspace_source": source,
        "workspace_initialized": initialized,
        "workspace_marker": marker.as_posix(),
        "expected_dirs": {
            name: (root / name).exists() and (root / name).is_dir()
            for name in expected_dirs
        },
    }


def init_workspace(workspace: str = "") -> dict[str, Any]:
    try:
        root, source, already_initialized = resolve_workspace_root(workspace)
        root.mkdir(parents=True, exist_ok=True)
        for dirname in ("tasks", "refs", "docs"):
            (root / dirname).mkdir(parents=True, exist_ok=True)

        meta_dir = root / WORKSPACE_META_DIR
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_file = meta_dir / WORKSPACE_META_FILE
        existing: dict[str, Any] = {}
        if meta_file.exists():
            try:
                existing = json.loads(meta_file.read_text(encoding="utf-8-sig"))
            except Exception:
                existing = {}

        created_at = existing.get("created_at") or now_iso()
        payload = {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "workspace_type": "cst_runtime_skill_workspace",
            "created_at": created_at,
            "updated_at": now_iso(),
            "skill_root_at_init": skill_root().as_posix(),
            "notes": [
                "This is a minimal CST runtime workspace.",
                "It is not a full CST_MCP repository.",
                "Production runs still require an explicit source_project .cst/.prj file.",
            ],
        }
        meta_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {
            "status": "success",
            "workspace_root": root.as_posix(),
            "workspace_source": source,
            "already_initialized": already_initialized,
            "workspace_marker": meta_file.as_posix(),
            "created_dirs": [(root / name).as_posix() for name in ("tasks", "refs", "docs")],
            "runtime_module": "cst_runtime.workspace",
        }
    except Exception as exc:
        return error_response("init_workspace_failed", str(exc), runtime_module="cst_runtime.workspace")


def safe_task_id(task_id: str) -> str:
    value = task_id.strip()
    if not value:
        raise ValueError("task_id is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if any(char not in allowed for char in value):
        raise ValueError("task_id may only contain letters, numbers, underscore, and hyphen")
    return value


def init_task(
    *,
    workspace: str = "",
    task_id: str,
    source_project: str,
    goal: str = "",
    title: str = "",
    force: bool = False,
) -> dict[str, Any]:
    try:
        workspace_result = init_workspace(workspace)
        if workspace_result.get("status") == "error":
            return workspace_result
        root = Path(str(workspace_result["workspace_root"]))
        resolved_task_id = safe_task_id(task_id)
        task_dir = root / "tasks" / resolved_task_id
        runs_dir = task_dir / "runs"
        task_json = task_dir / "task.json"
        if task_json.exists() and not force:
            return error_response(
                "task_already_exists",
                "task.json already exists; pass --force true or force=true to overwrite",
                task_path=task_dir.as_posix(),
                runtime_module="cst_runtime.workspace",
            )
        task_dir.mkdir(parents=True, exist_ok=True)
        runs_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "task_id": resolved_task_id,
            "title": title or goal or resolved_task_id,
            "goal": goal,
            "source_project": source_project,
            "created_at": now_iso(),
            "status": "initialized",
            "workspace_root": root.as_posix(),
        }
        task_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {
            "status": "success",
            "workspace_root": root.as_posix(),
            "task_id": resolved_task_id,
            "task_path": task_dir.as_posix(),
            "task_json": task_json.as_posix(),
            "runs_dir": runs_dir.as_posix(),
            "source_project": source_project,
            "source_project_exists": Path(source_project).expanduser().exists() if source_project else False,
            "runtime_module": "cst_runtime.workspace",
        }
    except Exception as exc:
        return error_response("init_task_failed", str(exc), runtime_module="cst_runtime.workspace")
