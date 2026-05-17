from __future__ import annotations

import json
import math
import re
import time
from html import escape
from pathlib import Path
from typing import Any

from .errors import error_response


# ── SVG chart renderers (no JS, no CDN, self-contained) ──

_SVG_W = 960
_SVG_H = 540
_SVG_MARGIN = dict(t=50, r=30, b=60, l=70)
_COLORS = ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"]
_DARK_BG = "#1f2937"
_DARK_TEXT = "#e5e7eb"
_LIGHT_BG = "#ffffff"
_LIGHT_TEXT = "#111827"


def _svg_axes(x_min: float, x_max: float, y_min: float, y_max: float, xlabel: str, ylabel: str, dark: bool) -> str:
    m = _SVG_MARGIN
    pw = _SVG_W - m["l"] - m["r"]
    ph = _SVG_H - m["t"] - m["b"]
    bg = _DARK_BG if dark else _LIGHT_BG
    tc = _DARK_TEXT if dark else _LIGHT_TEXT
    gc = "#374151" if dark else "#d1d5db"
    ac = "#9ca3af" if dark else "#6b7280"

    x_pad = (x_max - x_min) * 0.03 or 1
    y_pad = (y_max - y_min) * 0.05 or 1
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def sx(v: float) -> float: return m["l"] + (v - x_min) / (x_max - x_min) * pw
    def sy(v: float) -> float: return m["t"] + ph - (v - y_min) / (y_max - y_min) * ph

    lines = [f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" fill="{bg}" rx="8"/>']
    lines.append(f'<g fill="{tc}" font-family="Arial,sans-serif" font-size="13">')
    lines.append(f'<text x="{_SVG_W/2}" y="24" text-anchor="middle" font-size="16" font-weight="bold">{escape(xlabel)} vs {escape(ylabel)}</text>')
    lines.append("</g>")

    # Grid + Y axis labels
    y_steps = 5
    for i in range(y_steps + 1):
        v = y_min + (y_max - y_min) * i / y_steps
        yy = sy(v)
        lines.append(f'<line x1="{m["l"]}" y1="{yy}" x2="{m["l"]+pw}" y2="{yy}" stroke="{gc}" stroke-width="0.5"/>')
        lines.append(f'<text x="{m["l"]-6}" y="{yy+4}" text-anchor="end" fill="{ac}" font-family="Arial,sans-serif" font-size="11">{v:.2f}</text>')
    # Grid + X axis labels
    x_steps = 8
    for i in range(x_steps + 1):
        v = x_min + (x_max - x_min) * i / x_steps
        xx = sx(v)
        lines.append(f'<line x1="{xx}" y1="{m["t"]}" x2="{xx}" y2="{m["t"]+ph}" stroke="{gc}" stroke-width="0.5"/>')
        lines.append(f'<text x="{xx}" y="{m["t"]+ph+16}" text-anchor="middle" fill="{ac}" font-family="Arial,sans-serif" font-size="11">{v:.2f}</text>')
    # Axis labels
    lines.append(f'<text x="{m["l"]+pw/2}" y="{_SVG_H-6}" text-anchor="middle" fill="{tc}" font-family="Arial,sans-serif" font-size="13">{escape(xlabel)}</text>')
    lines.append(f'<text x="16" y="{m["t"]+ph/2}" text-anchor="middle" fill="{tc}" font-family="Arial,sans-serif" font-size="13" transform="rotate(-90,16,{m["t"]+ph/2})">{escape(ylabel)}</text>')

    return "\n".join(lines), x_min, x_max, y_min, y_max


def _svg_linechart(traces: list[dict[str, Any]], xlabel: str = "Frequency (GHz)", ylabel: str = "S11 (dB)", dark: bool = False) -> str:
    all_x = [v for t in traces for v in t.get("x", [])]
    all_y = [v for t in traces for v in t.get("y", [])]
    if not all_x or not all_y:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"><text x="20" y="40">No data</text></svg>'

    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)
    m = _SVG_MARGIN
    pw = _SVG_W - m["l"] - m["r"]
    ph = _SVG_H - m["t"] - m["b"]
    x_pad = (x_max - x_min) * 0.03 or 1
    y_pad = (y_max - y_min) * 0.05 or 1
    x_min -= x_pad; x_max += x_pad
    y_min -= y_pad; y_max += y_pad

    def sx(v): return m["l"] + (v - x_min) / (x_max - x_min) * pw
    def sy(v): return m["t"] + ph - (v - y_min) / (y_max - y_min) * ph

    axes_svg, _, _, _, _ = _svg_axes(all_x[0], all_x[-1] if len(all_x) > 1 else all_x[0] + 1, y_min + y_pad, y_max - y_pad, xlabel, ylabel, dark)
    parts = [axes_svg]

    for idx, trace in enumerate(traces):
        xs = trace.get("x", [])
        ys = trace.get("y", [])
        if not xs or not ys:
            continue
        color = _COLORS[idx % len(_COLORS)]
        pts = " ".join(f"{sx(x)},{sy(y)}" for x, y in zip(xs, ys) if not (math.isnan(y) or math.isinf(y)))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
        label = trace.get("name", f"Trace {idx+1}")
        ly = m["t"] + 20 + idx * 22
        parts.append(f'<line x1="{m["l"]+pw-120}" y1="{ly}" x2="{m["l"]+pw-100}" y2="{ly}" stroke="{color}" stroke-width="2"/>')
        tc = _DARK_TEXT if dark else _LIGHT_TEXT
        parts.append(f'<text x="{m["l"]+pw-94}" y="{ly+4}" fill="{tc}" font-family="Arial,sans-serif" font-size="12">{escape(label)}</text>')

    return f'<svg width="{_SVG_W}" height="{_SVG_H}" xmlns="http://www.w3.org/2000/svg">\n' + "\n".join(parts) + "\n</svg>"


def _svg_heatmap(x: list[float], y: list[float], z: list[list[float]], title: str, xlabel: str, ylabel: str, zlabel: str) -> str:
    if not x or not y or not z:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"><text x="20" y="40">No data</text></svg>'
    nx, ny = len(x), len(y)
    m = _SVG_MARGIN
    pw = _SVG_W - m["l"] - m["r"] - 60
    ph = _SVG_H - m["t"] - m["b"]
    cw, ch = pw / nx, ph / ny

    all_z = [v for row in z for v in row]
    z_min, z_max = min(all_z), max(all_z)
    z_rng = z_max - z_min or 1

    def _color(v):
        t = (v - z_min) / z_rng
        r = int(68 + (253 - 68) * t)
        g = int(1 + (231 - 1) * (1 - abs(t - 0.5) * 2))
        b = int(84 + (36 - 84) * (1 - t))
        return f"#{r:02x}{g:02x}{b:02x}"

    parts = [f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" fill="#ffffff" rx="8"/>']
    parts.append(f'<text x="{_SVG_W/2}" y="24" text-anchor="middle" font-size="16" font-weight="bold" font-family="Arial,sans-serif">{escape(title)}</text>')

    for i in range(ny):
        for j in range(nx):
            v = z[i][j] if i < len(z) and j < len(z[i]) else z_min
            xx = m["l"] + j * cw
            yy = m["t"] + i * ch
            parts.append(f'<rect x="{xx}" y="{yy}" width="{cw}" height="{ch}" fill="{_color(v)}" stroke="none"/>')

    # Colorbar
    cb_x = m["l"] + pw + 12
    cb_h = ph
    cb_steps = 20
    for i in range(cb_steps):
        t = i / cb_steps
        v = z_min + t * z_rng
        yy = m["t"] + cb_h - (cb_h * t)
        ch_step = cb_h / cb_steps + 1
        parts.append(f'<rect x="{cb_x}" y="{yy}" width="16" height="{ch_step}" fill="{_color(v)}" stroke="none"/>')
    parts.append(f'<text x="{cb_x+20}" y="{m["t"]+4}" fill="#111827" font-family="Arial,sans-serif" font-size="10">{z_max:.1f}</text>')
    parts.append(f'<text x="{cb_x+20}" y="{m["t"]+cb_h+4}" fill="#111827" font-family="Arial,sans-serif" font-size="10">{z_min:.1f}</text>')
    parts.append(f'<text x="{cb_x+20}" y="{m["t"]+cb_h/2+4}" fill="#111827" font-family="Arial,sans-serif" font-size="10" transform="rotate(-90,{cb_x+20},{m["t"]+cb_h/2+4})">{escape(zlabel)}</text>')

    tc = "#111827"
    x_step = max(1, nx // 8)
    for j in range(0, nx, x_step):
        parts.append(f'<text x="{m["l"]+j*cw+cw/2}" y="{m["t"]+ph+14}" text-anchor="middle" fill="{tc}" font-family="Arial,sans-serif" font-size="10">{x[j]:.1f}</text>')
    y_step = max(1, ny // 6)
    for i in range(0, ny, y_step):
        parts.append(f'<text x="{m["l"]-6}" y="{m["t"]+i*ch+ch/2+3}" text-anchor="end" fill="{tc}" font-family="Arial,sans-serif" font-size="10">{y[i]:.1f}</text>')
    parts.append(f'<text x="{m["l"]+pw/2}" y="{_SVG_H-6}" text-anchor="middle" fill="{tc}" font-family="Arial,sans-serif" font-size="12">{escape(xlabel)}</text>')
    parts.append(f'<text x="14" y="{m["t"]+ph/2}" text-anchor="middle" fill="{tc}" font-family="Arial,sans-serif" font-size="12" transform="rotate(-90,14,{m["t"]+ph/2})">{escape(ylabel)}</text>')

    return f'<svg width="{_SVG_W}" height="{_SVG_H}" xmlns="http://www.w3.org/2000/svg">\n' + "\n".join(parts) + "\n</svg>"


def _svg_page(title: str, body_svg: str, dark: bool = False, extra_html: str = "") -> str:
    bg = _DARK_BG if dark else _LIGHT_BG
    tc = _DARK_TEXT if dark else _LIGHT_TEXT
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: {bg}; color: {tc}; }}
    main {{ padding: 24px; max-width: 1024px; margin: 0 auto; }}
    h1 {{ margin: 0 0 18px; font-size: 22px; }}
    svg {{ max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.15); }}
    table {{ border-collapse: collapse; margin-top: 16px; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #374151; padding: 8px; text-align: left; }}
  </style>
</head>
<body>
<main>
  <h1>{escape(title)}</h1>
  {body_svg}
  {extra_html}
</main>
</body>
</html>"""


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


def list_subprojects(project_path: str, allow_interactive: bool = False) -> dict[str, Any]:
    try:
        project, context = _load_project(project_path, allow_interactive)
        subprojects = project.list_subprojects()
        return {
            "status": "success",
            "project_path": context["fullpath"],
            "count": len(subprojects),
            "subprojects": _serialize_value(subprojects),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "list_subprojects_failed",
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
            yaxis_title = "Magnitude (dB)" if y_kind == "magnitude_db" else str(payload.get("ylabel") or "Value")
            svg = _svg_linechart(
                [{"x": xdata, "y": ydata, "name": "value"}],
                xlabel=str(payload.get("xlabel") or "X"),
                ylabel=yaxis_title,
            )
            rendered_kind = "1d"
        elif "data" in payload:
            svg = _svg_heatmap(
                x=payload.get("xpositions") or [],
                y=payload.get("ypositions") or [],
                z=payload.get("data") or [],
                title=title,
                xlabel=str(payload.get("xlabel") or "X"),
                ylabel=str(payload.get("ylabel") or "Y"),
                zlabel=str(payload.get("zlabel") or "Value"),
            )
            rendered_kind = "2d"
        else:
            return error_response(
                "unsupported_export_payload",
                "JSON file does not contain xdata/ydata or 2D data",
                file_path=str(source),
                runtime_module="cst_runtime.results",
            )

        target.write_text(_svg_page(title, svg), encoding="utf-8")
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


def plot_project_result(
    project_path: str,
    treepath: str,
    module_type: str = "3d",
    run_id: int = 0,
    load_impedances: bool = True,
    output_html: str = "",
    page_title: str = "",
    allow_interactive: bool = False,
    subproject_treepath: str = "",
    result_kind: str = "auto",
    intermediate_json: str = "",
) -> dict[str, Any]:
    try:
        if not treepath:
            return error_response("treepath_missing", "treepath is required")
        output_target = Path(output_html).expanduser().resolve() if output_html else None
        if intermediate_json:
            export_path = Path(intermediate_json).expanduser().resolve()
        elif output_target is not None:
            export_path = output_target.with_suffix(".json")
        else:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            export_path = Path(project_path).expanduser().resolve().parent.parent / "exports" / f"project_result_{timestamp}.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)

        normalized_kind = (result_kind or "auto").strip().lower()
        attempts: list[tuple[str, dict[str, Any]]] = []
        if normalized_kind in {"auto", "1d", "0d/1d", "0d1d"}:
            attempts.append(
                (
                    "1d",
                    get_1d_result(
                        project_path=project_path,
                        treepath=treepath,
                        module_type=module_type,
                        run_id=run_id,
                        load_impedances=load_impedances,
                        export_path=str(export_path),
                        allow_interactive=allow_interactive,
                        subproject_treepath=subproject_treepath,
                    ),
                )
            )
        if normalized_kind in {"auto", "2d"} and (not attempts or attempts[-1][1].get("status") != "success"):
            attempts.append(
                (
                    "2d",
                    get_2d_result(
                        project_path=project_path,
                        treepath=treepath,
                        module_type=module_type,
                        export_path=str(export_path),
                        allow_interactive=allow_interactive,
                        subproject_treepath=subproject_treepath,
                    ),
                )
            )
        success = next(((kind, result) for kind, result in attempts if result.get("status") == "success"), None)
        if success is None:
            return error_response(
                "plot_project_result_export_failed",
                "could not export project result as 1D or 2D JSON",
                attempts=attempts,
                runtime_module="cst_runtime.results",
            )
        detected_kind, export_result = success
        plot_result = plot_exported_file(
            file_path=str(export_path),
            output_html=str(output_target or ""),
            page_title=page_title or f"CST Result Preview - {treepath}",
        )
        if plot_result.get("status") != "success":
            return plot_result
        return {
            **plot_result,
            "source": "project_result",
            "detected_kind": detected_kind,
            "project_path": str(Path(project_path).expanduser().resolve()),
            "treepath": treepath,
            "run_id": run_id,
            "module_type": module_type,
            "intermediate_json": str(export_path),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "plot_project_result_failed",
            str(exc),
            project_path=str(project_path),
            treepath=treepath,
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
        panel_svgs: list[str] = []
        for p in panels:
            panel_svgs.append(
                _svg_heatmap(p["x"], p["y"], p["z"], p["title"], p["xlabel"], p["ylabel"], p["zlabel"])
            )
        combined_svg = "\n".join(
            f'<div style="margin-bottom: 28px;">{s}</div>' for s in panel_svgs
        )
        target.write_text(_svg_page(title, combined_svg), encoding="utf-8")
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
        traces = [{"x": s["xdata"], "y": s["ydata"], "name": s["label"]} for s in all_series]
        table_html = (
            "<table><tr><th>Run</th><th>File</th><th>Best Freq</th><th>Min S11 dB</th></tr>"
            + "".join(
                f"<tr><td>{s['run_id']}</td><td>{escape(s['file'])}</td><td>{s['best_freq']}</td><td>{s['min_db']:.3f}</td></tr>"
                for s in all_series
            )
            + "</table>"
        )
        html_path.write_text(_svg_page(title, _svg_linechart(traces, dark=True), dark=True, extra_html=table_html), encoding="utf-8")
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


def _load_s11_series(file_paths: list[str]) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for index, file_path in enumerate(file_paths):
        path = Path(file_path).expanduser().resolve()
        if path.suffix.lower() != ".json":
            raise ValueError(f"S11 input must be .json: {path}")
        payload = _load_exported_payload(str(path))
        xdata = payload.get("xdata") or []
        ydata = payload.get("ydata") or []
        if not xdata or not ydata:
            raise ValueError(f"S11 input is missing xdata/ydata: {path}")
        db_values: list[float] = []
        for item in ydata:
            real, imag = _complex_components(item)
            db_values.append(_safe_log_db(math.hypot(real, imag)))
        run_id = payload.get("run_id")
        if run_id is None:
            match = re.search(r"run[_-]?(\d+)", path.stem, re.IGNORECASE)
            run_id = int(match.group(1)) if match else index + 1
        min_db = min(db_values)
        min_index = db_values.index(min_db)
        series.append(
            {
                "label": f"Run {run_id}",
                "run_id": run_id,
                "file": path.name,
                "file_path": str(path),
                "xdata": xdata,
                "ydata": db_values,
                "min_db": min_db,
                "best_freq": xdata[min_index] if min_index < len(xdata) else None,
            }
        )
    return series


def _load_dashboard_farfield_items(file_paths: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, file_path in enumerate(file_paths):
        path = Path(file_path).expanduser().resolve()
        payload = _load_exported_payload(str(path))
        if "data" not in payload:
            raise ValueError(f"farfield input must contain 2D grid data: {path}")
        metadata = payload.get("metadata") or {}
        run_id = metadata.get("run_id")
        if run_id is None:
            match = re.search(r"run[_-]?(\d+)", path.stem, re.IGNORECASE)
            run_id = int(match.group(1)) if match else index + 1
        items.append(
            {
                "run_id": run_id,
                "file": path.name,
                "file_path": str(path),
                "title": payload.get("title") or path.name,
                "xlabel": payload.get("xlabel") or "Phi (deg)",
                "ylabel": payload.get("ylabel") or "Theta (deg)",
                "zlabel": payload.get("zlabel") or metadata.get("source_quantity") or "Value",
                "x": payload.get("xpositions") or [],
                "y": payload.get("ypositions") or [],
                "z": payload.get("data") or [],
                "metadata": metadata,
            }
        )
    return items


def generate_s11_farfield_dashboard(
    s11_file_paths: list[str],
    farfield_file_paths: list[str],
    output_html: str = "",
    page_title: str = "",
    farfield_run_id: int = 0,
) -> dict[str, Any]:
    try:
        if not s11_file_paths:
            return error_response("s11_file_paths_missing", "s11_file_paths cannot be empty")
        if not farfield_file_paths:
            return error_response("farfield_file_paths_missing", "farfield_file_paths cannot be empty")

        s11_series = _load_s11_series(s11_file_paths)
        farfield_items = _load_dashboard_farfield_items(farfield_file_paths)
        selected_run_id = farfield_run_id or farfield_items[0]["run_id"]
        available_run_ids = {item["run_id"] for item in farfield_items}
        if selected_run_id not in available_run_ids:
            return error_response(
                "farfield_run_id_not_found",
                "farfield_run_id is not present in farfield_file_paths",
                farfield_run_id=selected_run_id,
                available_run_ids=sorted(available_run_ids),
                runtime_module="cst_runtime.results",
            )

        first_path = Path(s11_file_paths[0]).expanduser().resolve()
        target = Path(output_html).expanduser().resolve() if output_html else first_path.parent / "s11_farfield_dashboard.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        title = page_title or "S11 + Farfield Dashboard"
        s11_traces = [{"x": s["xdata"], "y": s["ydata"], "name": s["label"]} for s in s11_series]
        s11_svg = _svg_linechart(s11_traces, dark=False)

        farfield_svgs: list[str] = []
        for item in farfield_items:
            farfield_svgs.append(
                _svg_heatmap(item["x"], item["y"], item["z"], item["title"], item["xlabel"], item["ylabel"], item["zlabel"])
            )
        farfield_block = "\n".join(
            f'<div style="margin-bottom: 28px;">{s}</div>' for s in farfield_svgs
        )

        table_html = (
            "<table><tr><th>Run</th><th>S11 file</th><th>Best freq</th><th>Min S11 dB</th></tr>"
            + "".join(
                f"<tr><td>{s['run_id']}</td><td>{escape(s['file'])}</td><td>{s['best_freq']}</td><td>{s['min_db']:.3f}</td></tr>"
                for s in s11_series
            )
            + "</table>"
        )

        combined_svg = s11_svg + "\n" + farfield_block
        target.write_text(_svg_page(title, combined_svg, extra_html=table_html), encoding="utf-8")
        return {
            "status": "success",
            "output_html": str(target),
            "s11_series_count": len(s11_series),
            "farfield_file_count": len(farfield_items),
            "selected_farfield_run_id": selected_run_id,
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "generate_s11_farfield_dashboard_failed",
            str(exc),
            runtime_module="cst_runtime.results",
        )
