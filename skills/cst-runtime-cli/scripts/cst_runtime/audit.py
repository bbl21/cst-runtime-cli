from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import error_response
from .run_workspace import load_json_file, now_iso, resolve_run_dir, write_json_file


def parse_json_object_arg(value: Any, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError(f"{field_name} 必须是 JSON object 或 dict")


def safe_stage_filename(stage: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", stage.strip())
    normalized = normalized.strip("._")
    return normalized or "stage"


def json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return repr(value)


def record_run_stage(
    task_path: str,
    stage: str,
    run_id: str = "",
    status: str = "completed",
    message: str = "",
    details_json: str | dict[str, Any] = "",
    update_status: bool = True,
) -> dict[str, Any]:
    try:
        _, resolved_run_id, run_dir = resolve_run_dir(task_path, run_id)
        if not stage or not stage.strip():
            return error_response("stage_missing", "stage 不能为空")

        created_at = now_iso()
        details = parse_json_object_arg(details_json, "details_json")
        stage_payload = {
            "run_id": resolved_run_id,
            "stage": stage.strip(),
            "status": status,
            "message": message,
            "details": details,
            "recorded_at": created_at,
            "runtime_module": "cst_runtime.audit",
        }

        stages_dir = run_dir / "stages"
        logs_dir = run_dir / "logs"
        stages_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        stage_path = stages_dir / f"{safe_stage_filename(stage)}.json"
        write_json_file(stage_path, stage_payload)

        log_path = logs_dir / "production_chain.md"
        log_entry = [
            f"## {created_at} {stage.strip()}",
            "",
            f"- status: {status}",
        ]
        if message:
            log_entry.append(f"- message: {message}")
        if details:
            log_entry.append(f"- details: `{json.dumps(details, ensure_ascii=False)}`")
        log_entry.append("")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(log_entry) + "\n")

        status_path = run_dir / "status.json"
        if update_status and status_path.exists():
            status_payload = load_json_file(status_path)
            status_payload["stage"] = stage.strip()
            status_payload["status"] = status
            status_payload["updated_at"] = created_at
            write_json_file(status_path, status_payload)

        return {
            "status": "success",
            "run_id": resolved_run_id,
            "stage_path": stage_path.as_posix(),
            "log_path": log_path.as_posix(),
            "status_path": status_path.as_posix() if update_status else None,
            "runtime_module": "cst_runtime.audit",
        }
    except Exception as exc:
        return error_response("record_run_stage_failed", f"record_run_stage 失败: {str(exc)}")


def update_run_status(
    task_path: str,
    run_id: str = "",
    status: str = "",
    stage: str = "",
    best_result_json: str | dict[str, Any] = "",
    output_files_json: str | dict[str, Any] = "",
    error_json: str | dict[str, Any] = "",
    extra_json: str | dict[str, Any] = "",
    mark_completed: bool = False,
) -> dict[str, Any]:
    try:
        _, resolved_run_id, run_dir = resolve_run_dir(task_path, run_id)
        status_path = run_dir / "status.json"
        status_payload = load_json_file(status_path) or {"run_id": resolved_run_id}

        updated_at = now_iso()
        if status:
            status_payload["status"] = status
        if stage:
            status_payload["stage"] = stage

        best_result = parse_json_object_arg(best_result_json, "best_result_json")
        if best_result:
            status_payload["best_result"] = best_result

        output_files = parse_json_object_arg(output_files_json, "output_files_json")
        if output_files:
            current_outputs = status_payload.get("output_files")
            if not isinstance(current_outputs, dict):
                current_outputs = {}
            current_outputs.update(output_files)
            status_payload["output_files"] = current_outputs

        if error_json:
            status_payload["error"] = parse_json_object_arg(error_json, "error_json")
        elif status_payload.get("status") not in {"error", "blocked"}:
            status_payload["error"] = status_payload.get("error")

        extra = parse_json_object_arg(extra_json, "extra_json")
        for key, value in extra.items():
            status_payload[key] = value

        status_payload["updated_at"] = updated_at
        if mark_completed:
            status_payload["completed_at"] = updated_at

        write_json_file(status_path, status_payload)
        return {
            "status": "success",
            "run_id": resolved_run_id,
            "status_path": status_path.as_posix(),
            "run_status": status_payload,
            "runtime_module": "cst_runtime.audit",
        }
    except Exception as exc:
        return error_response("update_run_status_failed", f"update_run_status 失败: {str(exc)}")


def append_tool_call(
    *,
    run_dir: Path,
    adapter: str,
    tool_name: str,
    tool_args: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, str]:
    logs_dir = run_dir / "logs"
    stages_dir = run_dir / "stages"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stages_dir.mkdir(parents=True, exist_ok=True)

    audit_payload = {
        "timestamp": now_iso(),
        "adapter": adapter,
        "tool": tool_name,
        "args": tool_args,
        "status": result.get("status"),
        "result": result,
    }
    tool_calls_path = logs_dir / "tool_calls.jsonl"
    with tool_calls_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(audit_payload, ensure_ascii=False, default=json_default) + "\n")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stage_path = stages_dir / f"cli_{stamp}_{safe_stage_filename(tool_name)}.json"
    stage_path.write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    return {
        "tool_calls_jsonl": tool_calls_path.as_posix(),
        "stage_file": stage_path.as_posix(),
    }

