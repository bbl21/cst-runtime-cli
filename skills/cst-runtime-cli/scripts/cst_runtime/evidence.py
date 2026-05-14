from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import error_response

PYTHON = sys.executable


def _resolve_scripts_root() -> Path:
    return Path(__file__).resolve().parent


def _run_cli(args: list[str], cwd: str) -> dict[str, Any]:
    cli = _resolve_scripts_root().parent / "cst_runtime_cli.py"
    r = subprocess.run(
        [PYTHON, str(cli), *args],
        capture_output=True, text=True, cwd=cwd,
    )
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"_raw_stdout": r.stdout[:1000], "_raw_stderr": r.stderr[:500], "_returncode": r.returncode}


def _gather_evidence(project_path: str, capture_types: list[str], cwd: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ctype in capture_types:
        if ctype == "parameters":
            raw = _run_cli(["list-parameters", "--project-path", project_path], cwd)
            items.append({
                "type": "parameters",
                "command": f"list-parameters --project-path {project_path}",
                "status": raw.get("status", "error"),
                "data": raw.get("parameters", raw),
                "count": raw.get("count", 0),
            })
        elif ctype == "entities":
            raw = _run_cli(["list-entities", "--project-path", project_path], cwd)
            items.append({
                "type": "entities",
                "command": f"list-entities --project-path {project_path}",
                "status": raw.get("status", "error"),
                "data": raw.get("entities", raw),
                "count": raw.get("count", 0),
            })
        elif ctype == "file_info":
            p = Path(project_path)
            items.append({
                "type": "file_info",
                "path": str(p),
                "exists": p.exists(),
                "size_bytes": p.stat().st_size if p.exists() else None,
                "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat() if p.exists() else None,
            })
    return items


def capture_snapshot(
    project_path: str = "",
    capture_types: list[str] | None = None,
    output_dir: str = "",
    stage_name: str = "",
) -> dict[str, Any]:
    if not project_path:
        return error_response("project_path_required", "project_path is required")
    if not capture_types:
        return error_response("capture_types_required", "capture_types is required")

    cwd = str(Path.cwd())
    items = _gather_evidence(project_path, capture_types, cwd)

    snapshot = {
        "stage_name": stage_name or f"snapshot_{datetime.now().strftime('%H%M%S')}",
        "project_path": str(Path(project_path).resolve()),
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "capture_types": capture_types,
        "evidence": items,
        "note": "This is raw CLI output. Open CST GUI to verify.",
    }

    out_dir = Path(output_dir).resolve() if output_dir else Path(project_path).resolve().parent / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{snapshot['stage_name']}.json"
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    simple = {item["type"]: item.get("count") or item.get("data", {}) for item in items}
    return {
        "status": "success",
        "stage_name": snapshot["stage_name"],
        "output_file": str(out_path),
        "summary": simple,
        "tool": "stage-evidence",
        "adapter": "cst_runtime_cli",
    }


def _flatten_params(data: Any, indent: int = 0) -> str:
    if isinstance(data, dict):
        return "\n".join(f"{'  '*indent}{k} = {v}" for k, v in data.items())
    if isinstance(data, list):
        return "\n".join(f"{'  '*indent}{item}" for item in data)
    return str(data)


def compare_snapshots(
    before_file: str = "",
    after_file: str = "",
    output_html: str = "",
) -> dict[str, Any]:
    if not before_file or not after_file:
        return error_response("snapshot_files_required", "before_file and after_file are required")

    bf = Path(before_file)
    af = Path(after_file)
    if not bf.exists():
        return error_response("before_file_not_found", f"Before snapshot not found: {bf}")
    if not af.exists():
        return error_response("after_file_not_found", f"After snapshot not found: {af}")

    before = json.loads(bf.read_text(encoding="utf-8"))
    after = json.loads(af.read_text(encoding="utf-8"))

    html_parts: list[str] = []
    before_map = {e["type"]: e for e in before.get("evidence", [])}
    after_map = {e["type"]: e for e in after.get("evidence", [])}
    all_types = sorted(set(before_map) | set(after_map))

    for ctype in all_types:
        b_item = before_map.get(ctype, {})
        a_item = after_map.get(ctype, {})
        b_data = b_item.get("data", {})
        a_data = a_item.get("data", {})

        if ctype == "parameters":
            b_params = b_data if isinstance(b_data, dict) else {}
            a_params = a_data if isinstance(a_data, dict) else {}
            all_keys = sorted(set(b_params) | set(a_params))
            rows = ""
            for k in all_keys:
                bv = b_params.get(k, "—")
                av = a_params.get(k, "—")
                changed = bv != av
                cls = " class='changed'" if changed else ""
                rows += f"<tr{cls}><td>{k}</td><td>{bv}</td><td>{av}</td></tr>\n"
            html_parts.append(f"""
<h2>Parameters</h2>
<table><tr><th>Name</th><th>Before</th><th>After</th></tr>
{rows}</table>""")

        elif ctype == "entities":
            b_ents = b_data if isinstance(b_data, list) else []
            a_ents = a_data if isinstance(a_data, list) else []
            b_names = {f"{e.get('component','?')}:{e.get('name','?')}" for e in b_ents}
            a_names = {f"{e.get('component','?')}:{e.get('name','?')}" for e in a_ents}
            added = sorted(a_names - b_names)
            removed = sorted(b_names - a_names)
            changes = ""
            for e in added:
                changes += f"<tr class='added'><td>+</td><td>{e}</td></tr>\n"
            for e in removed:
                changes += f"<tr class='removed'><td>−</td><td>{e}</td></tr>\n"
            html_parts.append(f"""
<h2>Entities</h2>
<p>Before: {len(b_ents)} | After: {len(a_ents)}</p>
<table><tr><th></th><th>Name</th></tr>
{changes if changes else '<tr><td colspan="2">No changes</td></tr>'}</table>""")

        elif ctype == "file_info":
            b_fi = b_item.get("data", b_item)
            a_fi = a_item.get("data", a_item)
            html_parts.append(f"""
<h2>File Info</h2>
<table>
<tr><th>Property</th><th>Before</th><th>After</th></tr>
<tr><td>Exists</td><td>{b_fi.get('exists','?')}</td><td>{a_fi.get('exists','?')}</td></tr>
<tr><td>Size</td><td>{b_fi.get('size_bytes','?')}</td><td>{a_fi.get('size_bytes','?')}</td></tr>
<tr><td>Modified</td><td>{b_fi.get('modified','?')}</td><td>{a_fi.get('modified','?')}</td></tr>
</table>""")

    title = f"Evidence: {before.get('stage_name','?')} -to- {after.get('stage_name','?')}"
    project_path = after.get("project_path", "?")
    before_time = before.get("captured_at", "?")
    after_time = after.get("captured_at", "?")

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; background: #f8fafc; color: #111827; }}
  h1 {{ font-size: 20px; }}
  .meta {{ color: #4b5563; font-size: 13px; margin-bottom: 20px; }}
  h2 {{ font-size: 16px; margin-top: 28px; border-bottom: 1px solid #d1d5db; padding-bottom: 6px; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 800px; font-size: 13px; }}
  th, td {{ border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; }}
  th {{ background: #e5e7eb; }}
  .changed {{ background: #fef3c7; }}
  .added {{ background: #d1fae5; }}
  .removed {{ background: #fee2e2; }}
  .verify {{ margin-top: 24px; padding: 12px; background: #e0f2fe; border-radius: 6px; font-size: 14px; }}
</style>
</head>
<body>
<h1>Stage Evidence Report</h1>
<div class="meta">
  <p>Before: {before_time}<br>After: {after_time}<br>Project: {project_path}</p>
</div>
{''.join(html_parts)}
<div class="verify">
  <strong>Verify:</strong> Open CST Studio Suite, File &gt; Open, select project path above, manually check parameters and entities.
</div>
</body>
</html>"""

    if output_html:
        out = Path(output_html).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        result_path = str(out)
    else:
        out = af.parent / f"evidence_{af.stem}.html"
        out.write_text(html, encoding="utf-8")
        result_path = str(out)

    return {
        "status": "success",
        "output_html": result_path,
        "before_stage": before.get("stage_name", ""),
        "after_stage": after.get("stage_name", ""),
        "tool": "stage-evidence",
        "adapter": "cst_runtime_cli",
    }
