from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

from .errors import error_response


def _serialize_value(value: Any) -> Any:
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag, "complex_str": str(value)}
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if hasattr(value, "tolist"):
        return _serialize_value(value.tolist())
    return value


def _load_project(project_path: str, allow_interactive: bool = False, subproject_treepath: str = "") -> tuple[Any, dict[str, Any]]:
    import cst.results

    fullpath = str(Path(project_path).expanduser().resolve())
    project = cst.results.ProjectFile(fullpath, allow_interactive=allow_interactive)
    active_subproject = subproject_treepath or None
    if active_subproject:
        project = project.load_subproject(active_subproject)
    return project, {
        "fullpath": fullpath,
        "active_subproject": active_subproject,
        "allow_interactive": allow_interactive,
    }


def _get_result_module(project: Any, module_type: str) -> tuple[Any, str]:
    module_key = (module_type or "3d").lower()
    if module_key == "schematic":
        return project.get_schematic(), "schematic"
    return project.get_3d(), "3d"


def open_project(project_path: str, allow_interactive: bool = False, subproject_treepath: str = "") -> dict[str, Any]:
    try:
        path = Path(project_path).expanduser().resolve()
        if not path.is_file():
            return error_response(
                "project_file_missing",
                "project_path does not exist",
                project_path=path.as_posix(),
                runtime_module="cst_runtime.results",
            )
        project, context = _load_project(path.as_posix(), allow_interactive, subproject_treepath)
        return {
            "status": "success",
            "fullpath": context["fullpath"],
            "filename": project.filename,
            "allow_interactive": allow_interactive,
            "active_subproject": context["active_subproject"],
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "open_results_project_failed",
            str(exc),
            project_path=str(project_path),
            runtime_module="cst_runtime.results",
        )


def list_run_ids(
    project_path: str,
    treepath: str = "",
    module_type: str = "3d",
    allow_interactive: bool = False,
    subproject_treepath: str = "",
    skip_nonparametric: bool = False,
    max_mesh_passes_only: bool = True,
) -> dict[str, Any]:
    try:
        project, context = _load_project(project_path, allow_interactive, subproject_treepath)
        result_module, normalized_module = _get_result_module(project, module_type)
        if treepath:
            run_ids = result_module.get_run_ids(treepath, skip_nonparametric=skip_nonparametric)
        else:
            run_ids = result_module.get_all_run_ids(max_mesh_passes_only=max_mesh_passes_only)
        return {
            "status": "success",
            "project_path": context["fullpath"],
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": treepath or None,
            "count": len(run_ids),
            "run_ids": _serialize_value(run_ids),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "list_run_ids_failed",
            str(exc),
            project_path=str(project_path),
            runtime_module="cst_runtime.results",
        )


def get_parameter_combination(
    project_path: str,
    run_id: int,
    module_type: str = "3d",
    allow_interactive: bool = False,
    subproject_treepath: str = "",
) -> dict[str, Any]:
    try:
        project, context = _load_project(project_path, allow_interactive, subproject_treepath)
        result_module, normalized_module = _get_result_module(project, module_type)
        params = result_module.get_parameter_combination(int(run_id))
        return {
            "status": "success",
            "project_path": context["fullpath"],
            "run_id": int(run_id),
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "parameters": _serialize_value(params),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "get_parameter_combination_failed",
            str(exc),
            project_path=str(project_path),
            run_id=run_id,
            runtime_module="cst_runtime.results",
        )


def get_1d_result(
    project_path: str,
    treepath: str,
    module_type: str = "3d",
    run_id: int = 0,
    load_impedances: bool = True,
    export_path: str = "",
    allow_interactive: bool = False,
    subproject_treepath: str = "",
) -> dict[str, Any]:
    try:
        project, context = _load_project(project_path, allow_interactive, subproject_treepath)
        result_module, normalized_module = _get_result_module(project, module_type)
        result_item = result_module.get_result_item(
            treepath,
            run_id=int(run_id),
            load_impedances=load_impedances,
        )

        xdata = result_item.get_xdata()
        ydata = result_item.get_ydata()
        if export_path:
            export_file = Path(export_path).expanduser()
            if export_file.suffix.lower() != ".json":
                return error_response(
                    "invalid_export_extension",
                    "get_1d_result export_path only supports .json",
                    export_path=str(export_file),
                    runtime_module="cst_runtime.results",
                )
            export_file.parent.mkdir(parents=True, exist_ok=True)
            export_file = export_file.resolve()
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_file = (
                Path(context["fullpath"]).parent.parent / "exports" / f"result_1d_run{run_id}_{timestamp}.json"
            ).resolve()
            export_file.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "treepath": result_item.treepath,
            "title": result_item.title,
            "xlabel": result_item.xlabel,
            "ylabel": result_item.ylabel,
            "length": result_item.length,
            "run_id": result_item.run_id,
            "parameter_combination": _serialize_value(result_item.get_parameter_combination()),
            "xdata": _serialize_value(xdata),
            "ydata": _serialize_value(ydata),
        }
        export_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "status": "success",
            "mode": "local_export_only",
            "project_path": context["fullpath"],
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": result_item.treepath,
            "run_id": result_item.run_id,
            "point_count": len(xdata),
            "export_path": str(export_file),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "get_1d_result_failed",
            str(exc),
            project_path=str(project_path),
            treepath=treepath,
            run_id=run_id,
            runtime_module="cst_runtime.results",
        )


def _load_exported_payload(file_path: str) -> dict[str, Any]:
    return json.loads(Path(file_path).read_text(encoding="utf-8-sig"))


def _complex_components(value: Any) -> tuple[float, float]:
    if isinstance(value, dict):
        return float(value.get("real", 0.0)), float(value.get("imag", 0.0))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    if isinstance(value, (int, float)):
        return float(value), 0.0
    return 0.0, 0.0


def _safe_log_db(value: float) -> float:
    return 20.0 * math.log10(max(abs(value), 1e-15))


def generate_s11_comparison(
    file_paths: list[str],
    output_html: str = "",
    page_title: str = "",
) -> dict[str, Any]:
    try:
        if not file_paths:
            return error_response("file_paths_missing", "file_paths cannot be empty")

        all_series: list[dict[str, Any]] = []
        for index, file_path in enumerate(file_paths):
            path = Path(file_path)
            if path.suffix.lower() != ".json":
                return error_response(
                    "invalid_input_extension",
                    "generate_s11_comparison only supports .json inputs",
                    file_path=str(path),
                    runtime_module="cst_runtime.results",
                )
            payload = _load_exported_payload(str(path))
            xdata = payload.get("xdata") or []
            ydata = payload.get("ydata") or []
            if not xdata or not ydata:
                return error_response(
                    "invalid_s11_payload",
                    "input file is missing xdata/ydata",
                    file_path=str(path),
                    runtime_module="cst_runtime.results",
                )
            db_values = []
            for item in ydata:
                real, imag = _complex_components(item)
                db_values.append(_safe_log_db(math.hypot(real, imag)))
            payload_run_id = payload.get("run_id")
            if payload_run_id is None:
                match = re.search(r"run[_-]?(\d+)", path.stem, re.IGNORECASE)
                payload_run_id = int(match.group(1)) if match else index + 1
            min_db = min(db_values)
            min_index = db_values.index(min_db)
            all_series.append(
                {
                    "label": f"Run {payload_run_id}",
                    "run_id": payload_run_id,
                    "file": path.name,
                    "full_file": str(path.resolve()),
                    "xdata": xdata,
                    "ydata": db_values,
                    "min_db": min_db,
                    "best_freq": xdata[min_index] if min_index < len(xdata) else None,
                }
            )

        if output_html:
            html_path = Path(output_html).expanduser().resolve()
        else:
            html_path = Path(file_paths[0]).expanduser().resolve().parent / "s11_comparison.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)

        title = page_title or "S11 Comparison"
        series_json = json.dumps(all_series, ensure_ascii=False)
        html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>{title}</title>
  <script src=\"https://cdn.plot.ly/plotly-2.35.2.min.js\"></script>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #111827; color: #e5e7eb; }}
    main {{ padding: 24px; }}
    #plot {{ height: 70vh; min-height: 520px; }}
    table {{ border-collapse: collapse; margin-top: 16px; width: 100%; }}
    th, td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
<main>
  <h1>{title}</h1>
  <div id=\"plot\"></div>
  <table id=\"summary\"></table>
</main>
<script>
const series = {series_json};
const traces = series.map(s => ({{x: s.xdata, y: s.ydata, mode: 'lines', type: 'scatter', name: s.label}}));
Plotly.newPlot('plot', traces, {{
  title: 'S11 Comparison',
  xaxis: {{title: 'Frequency (GHz)'}},
  yaxis: {{title: 'S11 (dB)'}},
  paper_bgcolor: '#111827',
  plot_bgcolor: '#1f2937',
  font: {{color: '#e5e7eb'}},
  hovermode: 'x unified'
}}, {{responsive: true, displaylogo: false}});
document.getElementById('summary').innerHTML =
  '<tr><th>Run</th><th>File</th><th>Best Freq</th><th>Min S11 dB</th></tr>' +
  series.map(s => `<tr><td>${{s.run_id}}</td><td>${{s.file}}</td><td>${{s.best_freq}}</td><td>${{s.min_db.toFixed(3)}}</td></tr>`).join('');
</script>
</body>
</html>
"""
        html_path.write_text(html, encoding="utf-8")
        return {
            "status": "success",
            "output_html": str(html_path),
            "series_count": len(all_series),
            "series": [
                {
                    "run_id": item["run_id"],
                    "file": item["file"],
                    "min_db": item["min_db"],
                    "best_freq": item["best_freq"],
                }
                for item in all_series
            ],
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "generate_s11_comparison_failed",
            str(exc),
            runtime_module="cst_runtime.results",
        )
