from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import error_response


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json_file(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8-sig"))


def write_json_file(file_path: Path, payload: dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_next_run_index(runs_dir: Path) -> int:
    max_run_index = 0
    if runs_dir.exists():
        for child in runs_dir.iterdir():
            if not child.is_dir():
                continue
            match = re.fullmatch(r"run_(\d+)", child.name)
            if match:
                max_run_index = max(max_run_index, int(match.group(1)))
    return max_run_index + 1


def render_initial_summary(
    *,
    task_id: str,
    run_id: str,
    created_at: str,
    goal: str,
    target_metric: str,
    objective: str,
    frequency_start_ghz: float | None,
    frequency_end_ghz: float | None,
    source_project: Path,
    working_project: Path,
) -> str:
    lines = [
        f"# {run_id} Summary",
        "",
        "## Run Info",
        f"- run_id: {run_id}",
        f"- task_id: {task_id}",
        f"- created_at: {created_at}",
        f"- source_project: `{source_project.as_posix()}`",
        f"- working_project: `{working_project.as_posix()}`",
        "",
        "## Goal",
        goal or "TBD",
        "",
        "## Target Metrics",
        f"- primary: {target_metric or 'TBD'}",
        f"- objective: {objective or 'TBD'}",
    ]
    if frequency_start_ghz is not None or frequency_end_ghz is not None:
        lines.extend(
            [
                "",
                "## Frequency Range",
                f"- start_ghz: {frequency_start_ghz if frequency_start_ghz is not None else 'TBD'}",
                f"- end_ghz: {frequency_end_ghz if frequency_end_ghz is not None else 'TBD'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Status",
            "- status: prepared",
            "- next_step: open `projects/working.cst` and continue the simulation workflow",
            "",
            "## Notes",
            "- This run is created from a read-only source project copy.",
            "- Exported artifacts should be written into `exports/`.",
        ]
    )
    return "\n".join(lines) + "\n"


def copy_project_artifacts(source_project: Path, working_project: Path) -> Path:
    if source_project.suffix.lower() == ".prj":
        source_companion = source_project.parent
    else:
        source_companion = source_project.with_suffix("")
    if not source_companion.exists() or not source_companion.is_dir():
        raise FileNotFoundError(f"source companion directory not found: {source_companion}")

    lock_files = list(source_companion.rglob("*.lok"))
    if lock_files:
        raise RuntimeError("source project appears to be locked; close the CST project before copying")

    working_project.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_project, working_project)
    working_companion = working_project.with_suffix("")
    shutil.copytree(
        source_companion,
        working_companion,
        ignore=shutil.ignore_patterns("*.lok", "*.tmp"),
    )
    return working_companion


def resolve_run_dir(task_path: str, run_id: str = "") -> tuple[Path, str, Path]:
    task_dir = Path(task_path).expanduser().resolve()
    if not task_dir.exists() or not task_dir.is_dir():
        raise FileNotFoundError(f"task_path 不存在或不是目录: {task_path}")

    resolved_run_id = (run_id or "").strip()
    if not resolved_run_id:
        latest_path = task_dir / "latest"
        if not latest_path.exists():
            raise FileNotFoundError(f"未提供 run_id，且未找到 latest 文件: {latest_path}")
        resolved_run_id = latest_path.read_text(encoding="utf-8-sig").strip()
    resolved_run_id = resolved_run_id.lstrip("\ufeff")

    if not re.fullmatch(r"run_\d+", resolved_run_id):
        raise ValueError(f"run_id 格式错误，应为 run_xxx: {resolved_run_id}")

    run_dir = task_dir / "runs" / resolved_run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"run 目录不存在: {run_dir}")
    return task_dir, resolved_run_id, run_dir


def prepare_new_run(
    task_path: str,
    source_project: str = "",
    goal: str = "",
    target_metric: str = "",
    objective: str = "",
    frequency_start_ghz: float | None = None,
    frequency_end_ghz: float | None = None,
    allow_interactive: bool = True,
    save_project_after_simulation: bool = True,
) -> dict[str, Any]:
    try:
        task_dir = Path(task_path).expanduser().resolve()
        if not task_dir.exists() or not task_dir.is_dir():
            return error_response("task_path_missing", f"task_path 不存在或不是目录: {task_path}")

        task_json_path = task_dir / "task.json"
        task_data = load_json_file(task_json_path)
        task_id = task_data.get("task_id") or task_dir.name
        resolved_goal = goal or task_data.get("goal") or task_data.get("title") or ""

        resolved_source_project = source_project or task_data.get("source_project") or ""
        if not resolved_source_project:
            return error_response(
                "source_project_missing",
                "未提供 source_project，且 task.json 中未找到 source_project",
            )

        source_project_path = Path(resolved_source_project).expanduser().resolve()
        if source_project_path.is_dir():
            prj_files = [f for f in source_project_path.iterdir() if f.suffix.lower() == ".prj"]
            if prj_files:
                source_project_path = prj_files[0]
            else:
                return error_response(
                    "source_project_missing",
                    f"source_project 目录中没有找到 .prj 文件: {source_project_path.as_posix()}",
                    source_project=source_project_path.as_posix(),
                )
        elif source_project_path.suffix.lower() != ".cst" and source_project_path.suffix.lower() != ".prj":
            cst_path = source_project_path.with_suffix(".cst")
            prj_path = source_project_path.with_suffix(".prj")
            if cst_path.exists() and cst_path.is_file():
                source_project_path = cst_path
            elif prj_path.exists() and prj_path.is_file():
                source_project_path = prj_path
            else:
                return error_response(
                    "source_project_missing",
                    f"source_project 不存在: {source_project_path.as_posix()}",
                    source_project=source_project_path.as_posix(),
                )
        if not source_project_path.exists() or not source_project_path.is_file():
            return error_response(
                "source_project_missing",
                f"source_project 不存在: {source_project_path.as_posix()}",
                source_project=source_project_path.as_posix(),
            )

        runs_dir = task_dir / "runs"
        run_index = find_next_run_index(runs_dir)
        run_id = f"run_{run_index:03d}"
        run_dir = runs_dir / run_id
        projects_dir = run_dir / "projects"
        exports_dir = run_dir / "exports"
        logs_dir = run_dir / "logs"
        stages_dir = run_dir / "stages"
        analysis_dir = run_dir / "analysis"

        for path in [runs_dir, run_dir, projects_dir, exports_dir, logs_dir, stages_dir, analysis_dir]:
            path.mkdir(parents=True, exist_ok=True)

        working_project = projects_dir / "working.cst"
        working_companion = copy_project_artifacts(source_project_path, working_project)
        created_at = now_iso()

        config_payload = {
            "task_id": task_id,
            "run_id": run_id,
            "source_project": source_project_path.as_posix(),
            "working_project": working_project.resolve().as_posix(),
            "goal": resolved_goal,
            "target_metrics": {
                "primary": target_metric,
                "objective": objective,
            },
            "frequency_range": {
                "start_ghz": frequency_start_ghz,
                "end_ghz": frequency_end_ghz,
            },
            "allow_interactive": allow_interactive,
            "save_project_after_simulation": save_project_after_simulation,
            "created_at": created_at,
        }
        status_payload = {
            "task_id": task_id,
            "run_id": run_id,
            "status": "prepared",
            "stage": "workspace_prepared",
            "started_at": created_at,
            "completed_at": None,
            "best_result": None,
            "output_files": {},
            "error": None,
        }
        stage_payload = {
            "task_id": task_id,
            "run_id": run_id,
            "stage": "stage_00_workspace_prepared",
            "status": "prepared",
            "created_at": created_at,
            "source_project": source_project_path.as_posix(),
            "working_project": working_project.resolve().as_posix(),
            "working_project_dir": working_companion.resolve().as_posix(),
        }

        config_path = run_dir / "config.json"
        status_path = run_dir / "status.json"
        summary_path = run_dir / "summary.md"
        stage_path = stages_dir / "stage_00_workspace_prepared.json"
        log_path = logs_dir / "run_init.log"
        latest_path = task_dir / "latest"

        write_json_file(config_path, config_payload)
        write_json_file(status_path, status_payload)
        write_json_file(stage_path, stage_payload)
        summary_path.write_text(
            render_initial_summary(
                task_id=task_id,
                run_id=run_id,
                created_at=created_at,
                goal=resolved_goal,
                target_metric=target_metric,
                objective=objective,
                frequency_start_ghz=frequency_start_ghz,
                frequency_end_ghz=frequency_end_ghz,
                source_project=source_project_path,
                working_project=working_project.resolve(),
            ),
            encoding="utf-8",
        )
        log_path.write_text(
            (
                f"[{created_at}] prepared new run workspace\n"
                f"task_id={task_id}\n"
                f"run_id={run_id}\n"
                f"source_project={source_project_path.as_posix()}\n"
                f"working_project={working_project.resolve().as_posix()}\n"
            ),
            encoding="utf-8",
        )
        latest_path.write_text(run_id, encoding="utf-8")

        return {
            "status": "success",
            "task_id": task_id,
            "run_id": run_id,
            "run_dir": run_dir.resolve().as_posix(),
            "working_project": working_project.resolve().as_posix(),
            "working_project_dir": working_companion.resolve().as_posix(),
            "config_path": config_path.resolve().as_posix(),
            "status_path": status_path.resolve().as_posix(),
            "summary_path": summary_path.resolve().as_posix(),
            "latest_path": latest_path.resolve().as_posix(),
            "runtime_module": "cst_runtime.run_workspace",
            "message": f"已创建 {run_id} 并完成工程副本与初始化文档生成",
        }
    except Exception as exc:
        return error_response("prepare_new_run_failed", f"prepare_new_run 失败: {str(exc)}")


def get_run_context(task_path: str, run_id: str = "") -> dict[str, Any]:
    try:
        task_dir, resolved_run_id, run_dir = resolve_run_dir(task_path, run_id)
        config_path = run_dir / "config.json"
        status_path = run_dir / "status.json"
        working_project = run_dir / "projects" / "working.cst"
        return {
            "status": "success",
            "task_path": task_dir.as_posix(),
            "run_id": resolved_run_id,
            "run_dir": run_dir.as_posix(),
            "working_project": working_project.as_posix(),
            "projects_dir": (run_dir / "projects").as_posix(),
            "exports_dir": (run_dir / "exports").as_posix(),
            "logs_dir": (run_dir / "logs").as_posix(),
            "stages_dir": (run_dir / "stages").as_posix(),
            "analysis_dir": (run_dir / "analysis").as_posix(),
            "config_path": config_path.as_posix(),
            "status_path": status_path.as_posix(),
            "summary_path": (run_dir / "summary.md").as_posix(),
            "config": load_json_file(config_path),
            "run_status": load_json_file(status_path),
            "runtime_module": "cst_runtime.run_workspace",
        }
    except Exception as exc:
        return error_response("get_run_context_failed", f"get_run_context 失败: {str(exc)}")

