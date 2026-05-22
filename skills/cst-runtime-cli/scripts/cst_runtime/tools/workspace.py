"""workspace.py — workspace + run 工具定义"""
from . import _register_tool_defs


TOOL_DEFS = {
"get-run-context": {
    "category": "run",
    "risk": "read",
    "description": "Read standard run context through cst_runtime.",
    "handler": "tool_get_run_context",
    "json_schema": {
        "type": "object",
        "properties": {
            "task_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx"
                ]
            },
            "run_id": {
                "type": "string",
                "examples": [
                    ""
                ]
            }
        },
        "required": [
            "task_path",
            "run_id"
        ]
    },
},

"health-check": {
    "category": "workspace",
    "risk": "read",
    "description": "Run comprehensive environment diagnostics: Python, uv, workspace, CST libraries, imports. Auto-fixes what it can, reports remaining issues with user instructions.",
    "handler": "tool_health_check",
    "json_schema": {
        "type": "object",
        "properties": {
            "workspace": {
                "type": "string",
                "examples": [
                    ""
                ]
            },
            "auto_fix": {
                "type": "boolean",
                "examples": [
                    True
                ]
            }
        },
        "required": [
            "workspace",
            "auto_fix"
        ]
    },
},

"init-task": {
    "category": "workspace",
    "risk": "filesystem-write",
    "description": "Create a task.json and runs directory inside a runtime workspace.",
    "handler": "tool_init_task",
    "json_schema": {
        "type": "object",
        "properties": {
            "workspace": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\empty_workspace"
                ]
            },
            "task_id": {
                "type": "string",
                "examples": [
                    "task_001_demo"
                ]
            },
            "source_project": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\model.cst"
                ]
            },
            "goal": {
                "type": "string",
                "examples": [
                    "demo"
                ]
            },
            "title": {
                "type": "string",
                "examples": [
                    ""
                ]
            },
            "force": {
                "type": "boolean",
                "examples": [
                    False
                ]
            }
        },
        "required": [
            "workspace",
            "task_id",
            "source_project",
            "goal",
            "title",
            "force"
        ]
    },
},

"init-workspace": {
    "category": "workspace",
    "risk": "filesystem-write",
    "description": "Initialize a minimal CST runtime workspace in an empty or existing directory.",
    "handler": "tool_init_workspace",
    "json_schema": {
        "type": "object",
        "properties": {
            "workspace": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\empty_workspace"
                ]
            }
        },
        "required": [
            "workspace"
        ]
    },
},

"install-cst-libraries": {
    "category": "workspace",
    "risk": "filesystem-write",
    "description": "Install or verify CST Python libraries (cst, cst.results, cst.interface) using the uv-managed environment.",
    "handler": "tool_install_cst_libraries",
    "json_schema": {
        "type": "object",
        "properties": {
            "cst_path": {
                "type": "string",
                "examples": [
                    "C:\\Program Files\\CST Studio Suite 2026\\AMD64\\python_cst_libraries"
                ]
            },
            "dry_run": {
                "type": "boolean",
                "examples": [
                    True
                ]
            }
        },
        "required": [
            "cst_path",
            "dry_run"
        ]
    },
},

"prepare-run": {
    "category": "run",
    "risk": "filesystem-write",
    "description": "Create a standard run workspace through cst_runtime.",
    "handler": "tool_prepare_run",
    "json_schema": {
        "type": "object",
        "properties": {
            "task_path": {
                "type": "string",
                "examples": [
                    "C:\\path\\to\\tasks\\task_xxx"
                ]
            }
        },
        "required": [
            "task_path"
        ]
    },
},
}


# --- Handlers ---

from ..core import workspace as _ws
from ..core import workspace as _rw
from ..core import environment as _ce


def tool_init_workspace(args: dict) -> dict:
    result = _ws.init_workspace(str(args.get("workspace") or ""))
    if result.get("status") == "success":
        ws_root = result.get("workspace_root", "")
        cst_result = _ce.auto_register_cst(ws_root)
        result["cst_auto_registered"] = cst_result.get("cst_registered", False)
    return result


def tool_init_task(args: dict) -> dict:
    return _ws.init_task(
        workspace=str(args.get("workspace") or ""),
        task_id=str(args.get("task_id") or ""),
        source_project=str(args.get("source_project") or ""),
        goal=str(args.get("goal") or ""),
        title=str(args.get("title") or ""),
        force=bool(args.get("force", False)),
    )


def tool_prepare_run(args: dict) -> dict:
    return _rw.prepare_new_run(**args)


def tool_get_run_context(args: dict) -> dict:
    return _rw.get_run_context(**args)


def tool_install_cst_libraries(args: dict) -> dict:
    return _ce.install_cst_libraries(
        cst_path=str(args.get("cst_path", "")),
        dry_run=bool(args.get("dry_run", False)),
    )


def tool_health_check(args: dict) -> dict:
    return _ce.health_check(
        workspace=str(args.get("workspace", "")),
        auto_fix=bool(args.get("auto_fix", True)),
    )


_register_tool_defs(TOOL_DEFS)
