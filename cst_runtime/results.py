from __future__ import annotations

import json
import math
import re
import time
from html import escape
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


def get_version_info() -> dict[str, Any]:
    try:
        import cst.results

        return {
            "status": "success",
            "version_info": _serialize_value(cst.results.get_version_info()),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "get_version_info_failed",
            str(exc),
            runtime_module="cst_runtime.results",
        )


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


def list_result_items(
    project_path: str,
    module_type: str = "3d",
    filter_type: str = "0D/1D",
    allow_interactive: bool = False,
    subproject_treepath: str = "",
) -> dict[str, Any]:
    try:
        project, context = _load_project(project_path, allow_interactive, subproject_treepath)
        result_module, normalized_module = _get_result_module(project, module_type)
        normalized_filter = (filter_type or "0D/1D").strip()
        if normalized_filter.lower() == "all":
            all_items = result_module._get_all_result_items()
            treepaths: list[str] = []
            seen: set[str] = set()
            for item in all_items:
                treepath = getattr(item, "treepath", None)
                if not treepath or treepath in seen:
                    continue
                seen.add(treepath)
                treepaths.append(str(treepath))
            items = treepaths
        else:
            items = [str(item) for item in result_module.get_tree_items(filter=normalized_filter)]
        return {
            "status": "success",
            "project_path": context["fullpath"],
            "module_type": normalized_module,
            "filter_type": normalized_filter,
            "active_subproject": context["active_subproject"],
            "count": len(items),
            "items": items,
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "list_result_items_failed",
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


def get_2d_result(
    project_path: str,
    treepath: str,
    module_type: str = "3d",
    export_path: str = "",
    allow_interactive: bool = False,
    subproject_treepath: str = "",
    include_data: bool = False,
) -> dict[str, Any]:
    try:
        project, context = _load_project(project_path, allow_interactive, subproject_treepath)
        result_module, normalized_module = _get_result_module(project, module_type)
        result_2d = result_module.get_result2d_item(treepath)
        if export_path:
            export_file = Path(export_path).expanduser()
            if export_file.suffix.lower() != ".json":
                return error_response(
                    "invalid_export_extension",
                    "get_2d_result export_path only supports .json",
                    export_path=str(export_file),
                    runtime_module="cst_runtime.results",
                )
            export_file.parent.mkdir(parents=True, exist_ok=True)
            export_file = export_file.resolve()
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_file = (
                Path(context["fullpath"]).parent.parent
                / "exports"
                / f"result_2d_{result_2d.ny}x{result_2d.nx}_{timestamp}.json"
            ).resolve()
            export_file.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "treepath": treepath,
            "title": result_2d.title,
            "xlabel": result_2d.xlabel,
            "ylabel": result_2d.ylabel,
            "xunit": result_2d.xunit,
            "yunit": result_2d.yunit,
            "dataunit": result_2d.dataunit,
            "xmin": result_2d.xmin,
            "xmax": result_2d.xmax,
            "ymin": result_2d.ymin,
            "ymax": result_2d.ymax,
            "nx": result_2d.nx,
            "ny": result_2d.ny,
            "xpositions": _serialize_value(result_2d.get_xpositions()),
            "ypositions": _serialize_value(result_2d.get_ypositions()),
            "data": _serialize_value(result_2d.get_data()),
        }
        export_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "status": "success",
            "mode": "local_export_only",
            "project_path": context["fullpath"],
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": treepath,
            "nx": result_2d.nx,
            "ny": result_2d.ny,
            "export_path": str(export_file),
            "include_data_ignored": bool(include_data),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "get_2d_result_failed",
            str(exc),
            project_path=str(project_path),
            treepath=treepath,
            runtime_module="cst_runtime.results",
        )


def _load_exported_payload(file_path: str) -> dict[str, Any]:
    source = Path(file_path).expanduser().resolve()
    text = source.read_text(encoding="utf-8-sig", errors="replace")
    if source.suffix.lower() == ".json":
        return json.loads(text)
    parsed = _try_parse_cst_farfield_ascii(text, filename=source.name)
    if parsed is None:
        raise ValueError(f"unsupported exported file format: {source}")
    return parsed


def _try_parse_cst_farfield_ascii(text: str, filename: str = "") -> dict[str, Any] | None:
    lines = text.splitlines()
    if not lines:
        return None

    header = next((line.strip() for line in lines if "Theta" in line and "Phi" in line), "")
    if not header:
        return None

    quantity = "Value"
    unit = ""
    compact_header = re.sub(r"\s+", "", header)
    quantity_candidates = {
        "Abs(RealizedGain)": "Abs(Realized Gain)",
        "Abs(Gain)": "Abs(Gain)",
        "Abs(Directivity)": "Abs(Directivity)",
        "Abs(E)": "Abs(E)",
        "Abs(Theta)": "Abs(Theta)",
        "Abs(Phi)": "Abs(Phi)",
    }
    for compact_candidate, display_name in quantity_candidates.items():
        if compact_candidate in compact_header:
            quantity = display_name
            suffix = compact_header.split(compact_candidate, 1)[1]
            unit_match = re.search(r"\[([^\]]*)\]", suffix)
            unit = (unit_match.group(1).strip() if unit_match else "")
            break

    samples: dict[tuple[float, float], float] = {}
    theta_values: set[float] = set()
    phi_values: set[float] = set()
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            theta = float(parts[0])
            phi = float(parts[1])
            value = float(parts[2])
        except Exception:
            continue
        theta_values.add(theta)
        phi_values.add(phi)
        samples[(theta, phi)] = value

    if not samples:
        return None

    theta_sorted = sorted(theta_values)
    phi_sorted = sorted(phi_values)
    closure_added = False
    if len(phi_sorted) > 1 and abs(phi_sorted[0]) <= 1e-9 and 350.0 <= phi_sorted[-1] < 360.0:
        phi_sorted = [*phi_sorted, 360.0]
        closure_added = True

    grid: list[list[float | None]] = []
    for theta in theta_sorted:
        row: list[float | None] = []
        for phi in phi_sorted:
            source_phi = 0.0 if closure_added and abs(phi - 360.0) <= 1e-9 else phi
            row.append(samples.get((theta, source_phi)))
        grid.append(row)

    dataunit = unit or ("dBi" if quantity in {"Abs(Realized Gain)", "Abs(Gain)", "Abs(Directivity)"} else "")
    return {
        "kind": "2d",
        "title": filename or "CST Farfield",
        "xlabel": "Phi (deg)",
        "ylabel": "Theta (deg)",
        "zlabel": f"{quantity} ({dataunit})" if dataunit else quantity,
        "xpositions": phi_sorted,
        "ypositions": theta_sorted,
        "data": grid,
        "metadata": {
            "source_format": "cst_farfield_ascii",
            "source_quantity": quantity,
            "dataunit": dataunit,
            "point_count": len(samples),
            "theta_count": len(theta_sorted),
            "phi_count": len(phi_sorted),
            "closure_phi_360_added": closure_added,
        },
    }


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


def _plot_output_path(output_html: str, source_file: Path, prefix: str) -> Path:
    if output_html:
        target = Path(output_html).expanduser().resolve()
    else:
        target = source_file.expanduser().resolve().parent / f"{prefix}_{source_file.stem}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _scalar_series(values: list[Any]) -> tuple[list[float], str]:
    if not values:
        return [], "value"
    if any(isinstance(value, dict) and "real" in value and "imag" in value for value in values):
        return [_safe_log_db(math.hypot(*_complex_components(value))) for value in values], "magnitude_db"
    return [float(value) for value in values], "value"


def plot_exported_file(file_path: str, output_html: str = "", page_title: str = "") -> dict[str, Any]:
    try:
        source = Path(file_path).expanduser().resolve()
        payload = _load_exported_payload(str(source))
        title = page_title or payload.get("title") or f"Export Preview - {source.name}"
        target = _plot_output_path(output_html, source, "export_preview")

        if "xdata" in payload and "ydata" in payload:
            xdata = payload.get("xdata") or []
            ydata, y_kind = _scalar_series(payload.get("ydata") or [])
            plot_data = json.dumps({"x": xdata, "y": ydata}, ensure_ascii=False)
            yaxis_title = "Magnitude (dB)" if y_kind == "magnitude_db" else str(payload.get("ylabel") or "Value")
            body = f"""
const data = {plot_data};
Plotly.newPlot('plot', [{{x: data.x, y: data.y, type: 'scatter', mode: 'lines', name: 'value'}}], {{
  title: {json.dumps(title)},
  xaxis: {{title: {json.dumps(str(payload.get("xlabel") or "X"))}}},
  yaxis: {{title: {json.dumps(yaxis_title)}}},
  margin: {{t: 60, r: 24, b: 56, l: 72}}
}}, {{responsive: true, displaylogo: false}});
"""
            rendered_kind = "1d"
        elif "data" in payload:
            plot_data = json.dumps(
                {
                    "x": payload.get("xpositions") or [],
                    "y": payload.get("ypositions") or [],
                    "z": payload.get("data") or [],
                },
                ensure_ascii=False,
            )
            body = f"""
const data = {plot_data};
Plotly.newPlot('plot', [{{x: data.x, y: data.y, z: data.z, type: 'heatmap', colorscale: 'Viridis'}}], {{
  title: {json.dumps(title)},
  xaxis: {{title: {json.dumps(str(payload.get("xlabel") or "X"))}}},
  yaxis: {{title: {json.dumps(str(payload.get("ylabel") or "Y"))}}},
  margin: {{t: 60, r: 24, b: 56, l: 72}}
}}, {{responsive: true, displaylogo: false}});
"""
            rendered_kind = "2d"
        else:
            return error_response(
                "unsupported_export_payload",
                "JSON file does not contain xdata/ydata or 2D data",
                file_path=str(source),
                runtime_module="cst_runtime.results",
            )

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f8fafc; color: #111827; }}
    main {{ padding: 24px; }}
    #plot {{ height: 72vh; min-height: 520px; }}
  </style>
</head>
<body>
<main>
  <div id="plot"></div>
</main>
<script>
{body}
</script>
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return {
            "status": "success",
            "source": "exported_file",
            "file_path": str(source),
            "rendered_kind": rendered_kind,
            "output_html": str(target),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "plot_exported_file_failed",
            str(exc),
            file_path=str(file_path),
            runtime_module="cst_runtime.results",
        )


def plot_farfield_multi(
    file_paths: list[str],
    output_html: str = "",
    page_title: str = "",
) -> dict[str, Any]:
    try:
        if not file_paths:
            return error_response("file_paths_missing", "file_paths cannot be empty")

        panels: list[dict[str, Any]] = []
        for file_path in file_paths:
            source = Path(file_path).expanduser().resolve()
            payload = _load_exported_payload(str(source))
            if "data" not in payload:
                return error_response(
                    "unsupported_farfield_payload",
                    "farfield preview inputs must contain 2D grid data or CST farfield ASCII",
                    file_path=str(source),
                    runtime_module="cst_runtime.results",
                )
            metadata = payload.get("metadata") or {}
            panels.append(
                {
                    "file_path": str(source),
                    "file": source.name,
                    "title": payload.get("title") or source.name,
                    "xlabel": payload.get("xlabel") or "Phi (deg)",
                    "ylabel": payload.get("ylabel") or "Theta (deg)",
                    "zlabel": payload.get("zlabel") or metadata.get("source_quantity") or "Value",
                    "x": payload.get("xpositions") or [],
                    "y": payload.get("ypositions") or [],
                    "z": payload.get("data") or [],
                    "metadata": metadata,
                }
            )

        first_path = Path(file_paths[0]).expanduser().resolve()
        target = _plot_output_path(output_html, first_path, "farfield_multi")
        title = page_title or "Farfield Preview"
        panels_json = json.dumps(panels, ensure_ascii=False)
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f8fafc; color: #111827; }}
    main {{ padding: 24px; }}
    h1 {{ margin: 0 0 18px; font-size: 22px; }}
    .panel {{ margin: 0 0 28px; border-bottom: 1px solid #d1d5db; padding-bottom: 22px; }}
    .plot {{ height: 62vh; min-height: 460px; }}
    .meta {{ font-size: 13px; color: #4b5563; margin-bottom: 8px; }}
  </style>
</head>
<body>
<main>
  <h1>{escape(title)}</h1>
  <div id="panels"></div>
</main>
<script>
const panels = {panels_json};
const root = document.getElementById('panels');
panels.forEach((panel, idx) => {{
  const wrapper = document.createElement('section');
  wrapper.className = 'panel';
  const meta = panel.metadata || {{}};
  wrapper.innerHTML = `<h2>${{panel.title}}</h2><div class="meta">${{panel.file_path}} | ${{meta.source_quantity || panel.zlabel}} | theta=${{meta.theta_count || panel.y.length}}, phi=${{meta.phi_count || panel.x.length}}</div><div id="plot-${{idx}}" class="plot"></div>`;
  root.appendChild(wrapper);
  Plotly.newPlot(`plot-${{idx}}`, [{{x: panel.x, y: panel.y, z: panel.z, type: 'heatmap', colorscale: 'Viridis', colorbar: {{title: panel.zlabel}}}}], {{
    title: panel.title,
    xaxis: {{title: panel.xlabel}},
    yaxis: {{title: panel.ylabel}},
    margin: {{t: 60, r: 28, b: 56, l: 72}}
  }}, {{responsive: true, displaylogo: false}});
}});
</script>
</body>
</html>
"""
        target.write_text(html, encoding="utf-8")
        return {
            "status": "success",
            "output_html": str(target),
            "file_count": len(panels),
            "files": [
                {
                    "file_path": item["file_path"],
                    "theta_count": item["metadata"].get("theta_count"),
                    "phi_count": item["metadata"].get("phi_count"),
                    "source_quantity": item["metadata"].get("source_quantity"),
                    "dataunit": item["metadata"].get("dataunit"),
                }
                for item in panels
            ],
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "plot_farfield_multi_failed",
            str(exc),
            runtime_module="cst_runtime.results",
        )


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
