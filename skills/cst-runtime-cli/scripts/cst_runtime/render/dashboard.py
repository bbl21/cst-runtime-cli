from __future__ import annotations

import ast
import json
import math
import re
import time
from html import escape
from pathlib import Path
from typing import Any

from ..errors import error_response
from .svg_linechart import (
    _COLORS, _DARK_BG, _DARK_TEXT, _LIGHT_BG, _LIGHT_TEXT,
    _SVG_MARGIN, _SVG_W, _SVG_H,
    safe_log_db, complex_components, scalar_series,
    svg_linechart, svg_mini_trend,
)
from .svg_heatmap import svg_heatmap
from .svg_page import svg_page, metric_cards_html
from .canvas_3d import render_3d_farfield

_TIMELINE_TOOLS = {
    "change-parameter",
    "define-parameters",
    "define-brick", "define-cylinder", "define-cone", "define-sphere",
    "define-extrude-curve", "define-loft", "define-rectangle", "define-polygon-3d",
    "boolean-subtract", "boolean-add", "boolean-insert", "boolean-intersect",
    "delete-entity", "rename-entity",
    "start-simulation", "start-simulation-async",
    "get-1d-result",
    "stage-evidence",
}

_SECTION_LABELS = {
    "s11": "S11 曲线",
    "farfield": "3D 辐射方向图",
    "2d": "2D 场分布",
    "timeline": "操作审计追踪",
    "params": "参数变更记录",
    "efield": "电场分布",
    "surface_current": "表面电流",
    "voltage": "电压",
}


# ── File loading and parsing utilities ──


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


def _plot_output_path(output_html: str, source_file: Path, prefix: str) -> Path:
    if output_html:
        target = Path(output_html).expanduser().resolve()
    else:
        target = source_file.expanduser().resolve().parent / f"{prefix}_{source_file.stem}.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _parse_cli_filename(filename: str) -> dict[str, Any] | None:
    m = re.match(r"cli_(\d{8})_(\d{6})_(\d+)_(.+)\.json", filename)
    if not m:
        return None
    date_str, time_str, micro, tool = m.groups()
    ts = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}.{micro}"
    return {"timestamp": ts, "tool": tool.replace("_", "-"), "filename": filename, "sort_key": f"{date_str}{time_str}{micro}"}


def _build_timeline(run_dir: str) -> list[dict[str, Any]]:
    stages_dir = Path(run_dir) / "stages"
    if not stages_dir.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for fpath in sorted(stages_dir.iterdir()):
        info = _parse_cli_filename(fpath.name)
        if not info:
            continue
        if info["tool"] not in _TIMELINE_TOOLS:
            continue
        try:
            data = json.loads(fpath.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        info["status"] = data.get("status", "unknown")
        info["args"] = data.get("args", {})
        info["result"] = data.get("result", {})
        records.append(info)

    records.sort(key=lambda r: r["sort_key"])
    return records


def _categorize_step(record: dict[str, Any]) -> str:
    tool = record["tool"]
    if tool in {"change-parameter"}:
        return "param_change"
    if tool in {"define-parameters"}:
        return "param_define"
    if tool in {"define-brick", "define-cylinder", "define-cone", "define-sphere",
                 "define-extrude-curve", "define-loft", "define-rectangle", "define-polygon-3d"}:
        return "geometry"
    if tool.startswith("boolean-"):
        return "boolean"
    if tool in {"delete-entity", "rename-entity"}:
        return "entity"
    if tool in {"start-simulation", "start-simulation-async"}:
        return "simulation"
    if tool in {"get-1d-result"}:
        return "result"
    if tool in {"stage-evidence"}:
        return "evidence"
    return "other"


def _step_summary(record: dict[str, Any]) -> str:
    tool = record["tool"]
    args = record.get("args", {})
    if tool == "change-parameter":
        return f'{args.get("name", "?")} = {args.get("value", "?")}'
    if tool == "define-parameters":
        names = args.get("names", [])
        if isinstance(names, str):
            try:
                names = ast.literal_eval(names)
            except Exception:
                names = [names]
        return f'define {len(names)} params'
    if tool in {"define-brick", "define-cylinder", "define-cone", "define-sphere"}:
        return f'{args.get("name", "?")} ({args.get("material", "PEC")})'
    if tool.startswith("boolean-"):
        op = tool.replace("boolean-", "")
        return f'{op}: {args.get("target", "?")} / {args.get("tool", "?")}'
    if tool in {"delete-entity"}:
        return f'del {args.get("name", "?")}'
    if tool in {"start-simulation", "start-simulation-async"}:
        return "simulate"
    if tool in {"get-1d-result"}:
        return f'read S11 run={args.get("run_id", "?")}'
    if tool in {"stage-evidence"}:
        return f'capture: {args.get("stage_name", "?")}'
    return tool


def _rationale_from_step(record: dict[str, Any]) -> str:
    tool = record["tool"]
    args = record.get("args", {})
    if tool == "change-parameter":
        name = args.get("name", "")
        value = args.get("value", "")
        return f"修改参数 {name} = {value}"
    if tool == "define-parameters":
        return "定义优化参数"
    if tool in {"define-brick", "define-cylinder", "define-cone"}:
        name = args.get("name", "")
        return f"创建几何体 {name}"
    if tool.startswith("boolean-"):
        return "布尔运算，细化几何结构"
    if tool in {"delete-entity"}:
        return "删除冗余几何体"
    if tool in {"start-simulation", "start-simulation-async"}:
        return "启动仿真"
    if tool in {"get-1d-result"}:
        return "导出 S11 结果"
    if tool in {"stage-evidence"}:
        stage = args.get("stage_name", "")
        return f"快照：{stage}"
    return ""


def _load_s11_exports(export_dir: str) -> dict[int, dict[str, Any]]:
    exports: dict[int, dict[str, Any]] = {}
    d = Path(export_dir)
    if not d.is_dir():
        return exports
    for fpath in sorted(list(d.glob("s11_run*.json")) + list(d.glob("result_1d_run*.json"))):
        try:
            payload = json.loads(fpath.read_text(encoding="utf-8-sig"))
            if "xdata" not in payload or "ydata" not in payload:
                continue
            run_id = payload.get("run_id", 0)
            db_values: list[float] = []
            for item in payload.get("ydata", []):
                real = item.get("real", 0) if isinstance(item, dict) else float(item) if isinstance(item, (int, float)) else 0
                imag = item.get("imag", 0) if isinstance(item, dict) else 0
                db_values.append(safe_log_db(math.hypot(real, imag)))
            min_db = min(db_values)
            min_idx = db_values.index(min_db)
            exports[run_id] = {
                "run_id": run_id,
                "file": fpath.name,
                "file_path": str(fpath),
                "xdata": payload.get("xdata", []),
                "ydata": db_values,
                "min_db": min_db,
                "best_freq": payload.get("xdata", [])[min_idx] if min_idx < len(payload.get("xdata", [])) else None,
                "parameter_combination": payload.get("parameter_combination", {}),
            }
        except Exception:
            pass
    return exports


# ── HTML component builders ──


def _step_card_html(step_idx: int, record: dict[str, Any], s11_exports: dict[int, dict[str, Any]]) -> str:
    tool = record["tool"]
    category = _categorize_step(record)
    summary = _step_summary(record)
    rationale = _rationale_from_step(record)
    ts = record.get("timestamp", "")
    status = record.get("status", "unknown")
    args = record.get("args", {})
    result = record.get("result", {})

    status_badge = f'<span class="badge badge-{"success" if status == "success" else "warn"}">{"成功" if status == "success" else "失败"}</span>'

    detail_json = json.dumps({"tool": tool, "args": args, "result": result}, indent=2, ensure_ascii=False)

    s11_snippet = ""
    if category == "result":
        export_path = args.get("export_path", "")
        if export_path:
            try:
                payload = json.loads((Path(export_path) if Path(export_path).is_file() else Path(export_path).expanduser()).read_text(encoding="utf-8-sig"))
                if "xdata" in payload and "ydata" in payload:
                    xs = payload.get("xdata", [])
                    ys_raw = payload.get("ydata", [])
                    db_vals = []
                    for item in ys_raw:
                        real = item.get("real", 0) if isinstance(item, dict) else float(item) if isinstance(item, (int, float)) else 0
                        imag = item.get("imag", 0) if isinstance(item, dict) else 0
                        db_vals.append(safe_log_db(math.hypot(real, imag)))
                    if db_vals:
                        min_db = min(db_vals)
                        min_idx = db_vals.index(min_db)
                        best_freq = xs[min_idx] if min_idx < len(xs) else 0
                        s11_snippet = f'<div class="s11-snippet"><span class="s11-min">S11={min_db:.2f} dB</span> <span class="s11-freq">@ {best_freq:.3f} GHz</span></div>'
            except Exception:
                pass

    card_class = "step-card"
    if category == "param_change":
        card_class += " step-param"
    elif category == "simulation":
        card_class += " step-sim"
    elif category == "result":
        card_class += " step-result"

    html = f'''<div class="{card_class}">
  <div class="step-header">
    <span class="step-idx">#{step_idx}</span>
    <span class="step-tool {category}">{category}</span>
    {status_badge}
    <span class="step-ts">{ts}</span>
  </div>
  <div class="step-body">
    <div class="step-summary"><strong>{escape(summary)}</strong></div>
    {f'<div class="step-rationale">{escape(rationale)}</div>' if rationale else ''}
    {s11_snippet}
  </div>
  <details class="step-detail">
    <summary>原始 JSON</summary>
    <pre>{escape(detail_json)}</pre>
  </details>
</div>'''
    return html


def _optimization_s11_chart(s11_exports: dict[int, dict[str, Any]], dark: bool = False) -> str:
    if not s11_exports:
        return '<div class="chart-panel"><p>无 S11 导出数据</p></div>'
    traces = []
    for rid in sorted(s11_exports.keys()):
        e = s11_exports[rid]
        traces.append({"x": e["xdata"], "y": e["ydata"], "name": f"Run {rid}"})
    svg = svg_linechart(traces, dark=dark)
    return f'<div class="chart-panel">{svg}</div>'


def _s11_table_html(s11_exports: dict[int, dict[str, Any]]) -> str:
    if not s11_exports:
        return ""
    best = min(s11_exports.values(), key=lambda e: e["min_db"])
    rows = []
    for rid in sorted(s11_exports.keys()):
        e = s11_exports[rid]
        is_best = rid == best["run_id"]
        row_class = ' class="best"' if is_best else ""
        badge = '<span class="badge badge-best">最优</span>' if is_best else ""
        rows.append(
            f'<tr{row_class}><td>{rid}{badge}</td><td>{escape(e["file"])}</td><td>{e["best_freq"]:.3f} GHz</td><td>{e["min_db"]:.3f} dB</td></tr>'
        )
    return (
        f'<div class="data-section">'
        f'<div class="section-title">S11 结果</div>'
            f'<table><thead><tr><th>运行</th><th>文件</th><th>最优频率</th><th>最低 S11</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _optimization_metrics_html(s11_exports: dict[int, dict[str, Any]], timeline: list[dict[str, Any]]) -> str:
    metrics: list[dict[str, str]] = []
    if s11_exports:
        best = min(s11_exports.values(), key=lambda e: e["min_db"])
        metrics.append({"label": "最优 S11", "value": f"{best['min_db']:.2f}", "unit": "dB", "css_class": "success"})
        metrics.append({"label": "最优频率", "value": f"{best['best_freq']:.3f}" if best['best_freq'] else "-", "unit": "GHz", "css_class": "accent"})
        metrics.append({"label": "S11 运行", "value": str(len(s11_exports)), "css_class": ""})
    param_changes = [r for r in timeline if _categorize_step(r) == "param_change"]
    simulations = [r for r in timeline if _categorize_step(r) == "simulation"]
    if param_changes:
        metrics.append({"label": "参数变更", "value": str(len(param_changes)), "css_class": ""})
    if simulations:
        metrics.append({"label": "仿真次数", "value": str(len(simulations)), "css_class": ""})
    if timeline:
        freq_range = ""
        if s11_exports and len(s11_exports) > 0:
            any_e = next(iter(s11_exports.values()))
            if any_e["xdata"]:
                freq_range = f"{any_e['xdata'][0]:.2f} - {any_e['xdata'][-1]:.2f}"
        if freq_range:
            metrics.append({"label": "频率范围", "value": freq_range, "unit": "GHz", "css_class": ""})
    return metric_cards_html(metrics) if metrics else ""


def _param_changes_table_html(timeline: list[dict[str, Any]]) -> str:
    changes = [r for r in timeline if _categorize_step(r) == "param_change"]
    if not changes:
        return ""
    rows = []
    for r in changes:
        args = r.get("args", {})
        name = args.get("name", "?")
        value = args.get("value", "?")
        rows.append(f'<tr><td>{escape(str(name))}</td><td>{escape(str(value))}</td><td>{r.get("timestamp", "")}</td></tr>')
    return (
        f'<div class="data-section">'
        f'<div class="section-title">参数变更记录</div>'
        f'<table><thead><tr><th>参数</th><th>新值</th><th>时间</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table></div>"
    )


# ── S11/Farfield data loaders ──


def load_s11_series(file_paths: list[str]) -> list[dict[str, Any]]:
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
            real, imag = complex_components(item)
            db_values.append(safe_log_db(math.hypot(real, imag)))
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


def load_dashboard_farfield_items(file_paths: list[str]) -> list[dict[str, Any]]:
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


# ── Public API: plot exported file ──


def plot_exported_file(file_path: str, output_html: str = "", page_title: str = "") -> dict[str, Any]:
    try:
        source = Path(file_path).expanduser().resolve()
        payload = _load_exported_payload(str(source))
        title = page_title or payload.get("title") or f"Export Preview - {source.name}"
        target = _plot_output_path(output_html, source, "export_preview")

        if "xdata" in payload and "ydata" in payload:
            xdata = payload.get("xdata") or []
            ydata, y_kind = scalar_series(payload.get("ydata") or [])
            yaxis_title = "Magnitude (dB)" if y_kind == "magnitude_db" else str(payload.get("ylabel") or "Value")
            svg = svg_linechart(
                [{"x": xdata, "y": ydata, "name": "value"}],
                xlabel=str(payload.get("xlabel") or "X"),
                ylabel=yaxis_title,
            )
            rendered_kind = "1d"
        elif "data" in payload:
            svg = svg_heatmap(
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
                runtime_module="cst_runtime.render.dashboard",
            )

        target.write_text(svg_page(title, f'<div class="chart-panel">{svg}</div>'), encoding="utf-8")
        return {
            "status": "success",
            "source": "exported_file",
            "file_path": str(source),
            "rendered_kind": rendered_kind,
            "output_html": str(target),
            "runtime_module": "cst_runtime.render.dashboard",
        }
    except Exception as exc:
        return error_response(
            "plot_exported_file_failed",
            str(exc),
            file_path=str(file_path),
            runtime_module="cst_runtime.render.dashboard",
        )


# ── Public API: farfield multi ──


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
                    runtime_module="cst_runtime.render.dashboard",
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
                svg_heatmap(p["x"], p["y"], p["z"], p["title"], p["xlabel"], p["ylabel"], p["zlabel"])
            )
        grid_class = "chart-grid"
        if len(panel_svgs) >= 2:
            grid_class += " cols-2"
        combined_svg = f'<div class="{grid_class}">\n' + "\n".join(
            f'<div class="chart-panel">{s}</div>' for s in panel_svgs
        ) + "\n</div>"
        target.write_text(svg_page(title, combined_svg), encoding="utf-8")
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
            "runtime_module": "cst_runtime.render.dashboard",
        }
    except Exception as exc:
        return error_response(
            "plot_farfield_multi_failed",
            str(exc),
            runtime_module="cst_runtime.render.dashboard",
        )


# ── Public API: S11 comparison ──


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
                    "S11 comparison only supports .json inputs",
                    file_path=str(path),
                    runtime_module="cst_runtime.render.dashboard",
                )
            payload = _load_exported_payload(str(path))
            xdata = payload.get("xdata") or []
            ydata = payload.get("ydata") or []
            if not xdata or not ydata:
                return error_response(
                    "invalid_s11_payload",
                    "input file is missing xdata/ydata",
                    file_path=str(path),
                    runtime_module="cst_runtime.render.dashboard",
                )
            db_values = []
            for item in ydata:
                real, imag = complex_components(item)
                db_values.append(safe_log_db(math.hypot(real, imag)))
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

        best_series = min(all_series, key=lambda s: s["min_db"])
        freq_min = min(s["xdata"][0] for s in all_series if s["xdata"])
        freq_max = max(s["xdata"][-1] for s in all_series if s["xdata"])
        freq_range = f"{freq_min:.3f} - {freq_max:.3f}"

        metrics = [
            {"label": "最优 S11", "value": f"{best_series['min_db']:.2f}", "unit": "dB", "css_class": "success"},
            {"label": "最优频率", "value": f"{best_series['best_freq']:.3f}" if best_series['best_freq'] else "-", "unit": "GHz", "css_class": "accent"},
            {"label": "对比数量", "value": str(len(all_series)), "css_class": ""},
            {"label": "频率范围", "value": freq_range, "unit": "GHz", "css_class": ""},
        ]
        metrics_html_str = metric_cards_html(metrics)

        table_rows = []
        for s in all_series:
            is_best = s["run_id"] == best_series["run_id"]
            row_class = ' class="best"' if is_best else ""
            badge = '<span class="badge badge-best">最优</span>' if is_best else ""
            table_rows.append(
                f'<tr{row_class}><td>{s["run_id"]}{badge}</td><td>{escape(s["file"])}</td><td>{s["best_freq"]:.3f} GHz</td><td>{s["min_db"]:.3f} dB</td></tr>'
            )
        table_html = (
            f'<div class="data-section">'
            f'<div class="section-title">运行汇总</div>'
            f'<table><thead><tr><th>运行</th><th>文件</th><th>最优频率</th><th>最低 S11</th></tr></thead><tbody>'
            + "".join(table_rows)
            + "</tbody></table></div>"
        )

        body_svg = f'<div class="chart-panel">{svg_linechart(traces, dark=True)}</div>'
        html_path.write_text(
            svg_page(title, body_svg, dark=True, extra_html=table_html, metrics_html=metrics_html_str,
                      subtitle=f"对比 {len(all_series)} 个 S11 结果"),
            encoding="utf-8")
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
            "runtime_module": "cst_runtime.render.dashboard",
        }
    except Exception as exc:
        return error_response(
            "generate_s11_comparison_failed",
            str(exc),
            runtime_module="cst_runtime.render.dashboard",
        )


# ── Public API: combined S11 + farfield dashboard ──


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

        s11_series = load_s11_series(s11_file_paths)
        farfield_items = load_dashboard_farfield_items(farfield_file_paths)
        selected_run_id = farfield_run_id or farfield_items[0]["run_id"]
        available_run_ids = {item["run_id"] for item in farfield_items}
        if selected_run_id not in available_run_ids:
            return error_response(
                "farfield_run_id_not_found",
                "farfield_run_id is not present in farfield_file_paths",
                farfield_run_id=selected_run_id,
                available_run_ids=sorted(available_run_ids),
                runtime_module="cst_runtime.render.dashboard",
            )

        first_path = Path(s11_file_paths[0]).expanduser().resolve()
        target = Path(output_html).expanduser().resolve() if output_html else first_path.parent / "s11_farfield_dashboard.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        title = page_title or "S11 + Farfield Dashboard"
        s11_traces = [{"x": s["xdata"], "y": s["ydata"], "name": s["label"]} for s in s11_series]
        s11_svg = svg_linechart(s11_traces, dark=False)

        farfield_panels: list[str] = []
        for item in farfield_items:
            farfield_panels.append(
                f'<div class="chart-panel">'
                f'{svg_heatmap(item["x"], item["y"], item["z"], item["title"], item["xlabel"], item["ylabel"], item["zlabel"])}'
                f'</div>'
            )
        ff_grid_class = "chart-grid"
        if len(farfield_panels) >= 2:
            ff_grid_class += " cols-2"
        farfield_block = f'<div class="{ff_grid_class}">\n' + "\n".join(farfield_panels) + "\n</div>"

        best_s11 = min(s11_series, key=lambda s: s["min_db"])
        freq_min = min(s["xdata"][0] for s in s11_series if s["xdata"])
        freq_max = max(s["xdata"][-1] for s in s11_series if s["xdata"])
        metrics = [
            {"label": "最优 S11", "value": f"{best_s11['min_db']:.2f}", "unit": "dB", "css_class": "success"},
            {"label": "最优频率", "value": f"{best_s11['best_freq']:.3f}" if best_s11['best_freq'] else "-", "unit": "GHz", "css_class": "accent"},
            {"label": "S11 运行", "value": str(len(s11_series)), "css_class": ""},
            {"label": "远场面板", "value": str(len(farfield_items)), "css_class": ""},
            {"label": "频率范围", "value": f"{freq_min:.3f} - {freq_max:.3f}", "unit": "GHz", "css_class": ""},
        ]
        metrics_html_str = metric_cards_html(metrics)

        table_rows = []
        for s in s11_series:
            is_best = s["run_id"] == best_s11["run_id"]
            row_class = ' class="best"' if is_best else ""
            badge = '<span class="badge badge-best">最优</span>' if is_best else ""
            table_rows.append(
                f'<tr{row_class}><td>{s["run_id"]}{badge}</td><td>{escape(s["file"])}</td><td>{s["best_freq"]:.3f} GHz</td><td>{s["min_db"]:.3f} dB</td></tr>'
            )
        table_html = (
            f'<div class="data-section">'
            f'<div class="section-title">S11 汇总</div>'
            f'<table><thead><tr><th>运行</th><th>S11 文件</th><th>最优频率</th><th>最低 S11</th></tr></thead><tbody>'
            + "".join(table_rows)
            + "</tbody></table></div>"
        )

        body_svg_content = f'<div class="chart-panel">{s11_svg}</div>\n{farfield_block}'
        target.write_text(
            svg_page(title, body_svg_content, extra_html=table_html, metrics_html=metrics_html_str,
                      subtitle=f"S11 运行：{len(s11_series)} | 远场面板：{len(farfield_items)}"),
            encoding="utf-8")
        return {
            "status": "success",
            "output_html": str(target),
            "s11_series_count": len(s11_series),
            "farfield_file_count": len(farfield_items),
            "selected_farfield_run_id": selected_run_id,
            "runtime_module": "cst_runtime.render.dashboard",
        }
    except Exception as exc:
        return error_response(
            "generate_s11_farfield_dashboard_failed",
            str(exc),
            runtime_module="cst_runtime.render.dashboard",
        )


# ── Public API: optimization dashboard ──


def generate_optimization_dashboard(
    run_dir: str,
    farfield_files: list[str] | None = None,
    output_html: str = "",
    page_title: str = "",
) -> dict[str, Any]:
    try:
        rd = Path(run_dir).expanduser().resolve()
        if not rd.is_dir():
            return error_response("run_dir_missing", "run_dir does not exist", run_dir=str(rd))

        exports_dir = rd / "exports"
        s11_exports = _load_s11_exports(str(exports_dir))
        timeline = _build_timeline(str(rd))

        ff_data: dict[str, Any] = {}
        if farfield_files:
            for ff_path in farfield_files:
                try:
                    ff_data = _load_exported_payload(str(Path(ff_path).expanduser().resolve()))
                    break
                except Exception:
                    pass
        else:
            for ff_file in sorted(exports_dir.glob("farfield_*.txt")):
                try:
                    ff_data = _load_exported_payload(str(ff_file))
                    break
                except Exception:
                    pass

        target = Path(output_html).expanduser().resolve() if output_html else rd.parent.parent / "exports" / "optimization_dashboard.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        title = page_title or f"Optimization Dashboard — {rd.parent.parent.name} / {rd.name}"

        metrics_html_str = _optimization_metrics_html(s11_exports, timeline)
        s11_chart = _optimization_s11_chart(s11_exports)

        ff_3d = ""
        if ff_data:
            ff_3d = (
                f'<div class="chart-panel">'
                f'<h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em">3D 辐射方向图</h3>'
                f'<div style="margin-bottom:8px;display:flex;gap:8px;flex-wrap:wrap">'
                f'<button onclick="document.getElementById(\'ff3d_dash\').resetView()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">重置</button>'
                f'<button onclick="document.getElementById(\'ff3d_dash\').startAuto()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">自动旋转</button>'
                f'</div>'
                f'{render_3d_farfield(ff_data, "ff3d_dash")}'
                f'</div>'
            )

        trend_html = ""
        if len(s11_exports) > 1:
            min_dbs = [s11_exports[rid]["min_db"] for rid in sorted(s11_exports.keys())]
            trend_svg_str = svg_mini_trend(min_dbs, label="S11 per iteration")
            trend_html = f'<div class="chart-panel"><h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em">收敛趋势</h3>{trend_svg_str}</div>'

        param_table = _param_changes_table_html(timeline)
        s11_table = _s11_table_html(s11_exports)

        step_previews: list[str] = []
        significant = [r for r in timeline if _categorize_step(r) in {"param_change", "simulation", "result"}]
        for idx, r in enumerate(significant[-12:]):
            step_previews.append(_step_card_html(len(significant) - len(significant[-12:]) + idx + 1, r, s11_exports))
        timeline_preview_html = ""
        if step_previews:
            timeline_preview_html = (
                '<div class="section-title">近期操作</div>'
                '<div class="step-list">' + "\n".join(step_previews) + '</div>'
            )

        body = (
            f'{s11_chart}\n'
            f'{ff_3d}\n'
            f'{trend_html}\n'
            f'{param_table}\n'
            f'{s11_table}\n'
            f'{timeline_preview_html}'
        )

        target.write_text(
            svg_page(title, body, extra_html="", metrics_html=metrics_html_str,
                      subtitle=f"优化运行：{rd.name} | S11 运行：{len(s11_exports)} | 参数变更：{sum(1 for r in timeline if _categorize_step(r) == 'param_change')}"),
            encoding="utf-8")

        return {
            "status": "success",
            "output_html": str(target),
            "s11_count": len(s11_exports),
            "timeline_count": len(timeline),
            "has_farfield_3d": bool(ff_data),
            "runtime_module": "cst_runtime.render.dashboard",
        }
    except Exception as exc:
        return error_response(
            "generate_optimization_dashboard_failed",
            str(exc),
            run_dir=str(run_dir),
            runtime_module="cst_runtime.render.dashboard",
        )


# ── Public API: optimization audit ──


def generate_optimization_audit(
    run_dir: str,
    farfield_files: list[str] | None = None,
    output_html: str = "",
    page_title: str = "",
) -> dict[str, Any]:
    try:
        rd = Path(run_dir).expanduser().resolve()
        if not rd.is_dir():
            return error_response("run_dir_missing", "run_dir does not exist", run_dir=str(rd))

        exports_dir = rd / "exports"
        s11_exports = _load_s11_exports(str(exports_dir))
        timeline = _build_timeline(str(rd))

        ff_data: dict[str, Any] = {}
        if farfield_files:
            for ff_path in farfield_files:
                try:
                    ff_data = _load_exported_payload(str(Path(ff_path).expanduser().resolve()))
                    break
                except Exception:
                    pass
        else:
            for ff_file in sorted(exports_dir.glob("farfield_*.txt")):
                try:
                    ff_data = _load_exported_payload(str(ff_file))
                    break
                except Exception:
                    pass

        target = Path(output_html).expanduser().resolve() if output_html else rd.parent.parent / "exports" / "optimization_audit.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        title = page_title or f"Optimization Audit Trail — {rd.parent.parent.name} / {rd.name}"

        metrics_html_str = _optimization_metrics_html(s11_exports, timeline)

        ff_full = ""
        if ff_data:
            ff_full = (
                f'<div class="chart-panel">'
                f'<h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em">3D 辐射方向图</h3>'
                f'<div style="margin-bottom:8px;display:flex;gap:8px;flex-wrap:wrap">'
                f'<button onclick="document.getElementById(\'ff3d_audit\').resetView()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">重置</button>'
                f'<button onclick="document.getElementById(\'ff3d_audit\').startAuto()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">自动旋转</button>'
                f'</div>'
                f'{render_3d_farfield(ff_data, "ff3d_audit")}'
                f'</div>'
            )

        s11_chart = _optimization_s11_chart(s11_exports)

        step_cards: list[str] = []
        for idx, r in enumerate(timeline, 1):
            step_cards.append(_step_card_html(idx, r, s11_exports))
        step_list_html = ""
        if step_cards:
            step_list_html = (
                f'<div class="section-title">完整审计追踪 ({len(step_cards)} 条操作)</div>'
                '<div class="step-list">' + "\n".join(step_cards) + '</div>'
            )

        s11_table = _s11_table_html(s11_exports)
        param_table = _param_changes_table_html(timeline)

        body = (
            f'{ff_full}\n'
            f'{s11_chart}\n'
            f'{param_table}\n'
            f'{s11_table}\n'
            f'{step_list_html}'
        )

        target.write_text(
            svg_page(title, body, extra_html="", metrics_html=metrics_html_str,
                      subtitle=f"优化运行：{rd.name} | {len(timeline)} 操作 | {len(s11_exports)} 个 S11 导出"),
            encoding="utf-8")

        return {
            "status": "success",
            "output_html": str(target),
            "s11_count": len(s11_exports),
            "timeline_count": len(timeline),
            "has_farfield_3d": bool(ff_data),
            "runtime_module": "cst_runtime.render.dashboard",
        }
    except Exception as exc:
        return error_response(
            "generate_optimization_audit_failed",
            str(exc),
            run_dir=str(run_dir),
            runtime_module="cst_runtime.render.dashboard",
        )


# ── Public API: generate_report report ──


def generate_report(
    data_dir: str,
    output_html: str = "",
    page_title: str = "",
) -> dict[str, Any]:
    try:
        dd = Path(data_dir).expanduser().resolve()
        exports_d = dd / "exports"
        if not exports_d.is_dir():
            exports_d = dd
        target = Path(output_html).expanduser().resolve() if output_html else exports_d / "report.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        title = page_title or f"电磁仿真报告 — {dd.name}"

        body_parts: list[str] = []
        metrics: list[dict[str, str]] = []

        # S11 section
        s11_files = sorted(list(exports_d.glob("s11_run*.json")) + list(exports_d.glob("result_1d_run*.json")))
        s11_data = _load_s11_exports(str(exports_d)) if s11_files else {}
        if s11_data:
            s11_traces = [{"x": e["xdata"], "y": e["ydata"], "name": f"Run {e['run_id']}"} for e in s11_data.values()]
            s11_svg = svg_linechart(s11_traces)
            body_parts.append(f'<h2 class="section-h2">{_SECTION_LABELS["s11"]}</h2><div class="chart-panel">{s11_svg}</div>')
            best = min(s11_data.values(), key=lambda e: e["min_db"])
            metrics.append({"label": "最优 S11", "value": f"{best['min_db']:.2f}", "unit": "dB", "css_class": "success"})
            metrics.append({"label": "最优频率", "value": f"{best['best_freq']:.3f}" if best['best_freq'] else "-", "unit": "GHz", "css_class": "accent"})
            metrics.append({"label": "S11 文件数", "value": str(len(s11_data)), "css_class": ""})

        # Farfield section
        ff_files = sorted(exports_d.glob("farfield*.txt"))
        if ff_files:
            body_parts.append(f'<h2 class="section-h2">{_SECTION_LABELS["farfield"]}</h2>')
            if len(ff_files) > 1:
                opts = "".join(f'<option value="{i}">{ff.name}</option>' for i, ff in enumerate(ff_files))
                body_parts.append(f'<select id="ffSelect" onchange="switchFF(this.value)" style="margin-bottom:12px;padding:6px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);font-size:13px">{opts}</select>')
            for i, ff_file in enumerate(ff_files):
                try:
                    ff_data = _load_exported_payload(str(ff_file))
                    display = "block" if i == 0 else "none"
                    body_parts.append(f'<div class="ff-panel" id="ffPanel{i}" style="display:{display}">{render_3d_farfield(ff_data, f"ff3d_{i}")}</div>')
                except Exception:
                    pass
            if len(ff_files) > 1:
                body_parts.append('<script>function switchFF(v){var ps=document.querySelectorAll(".ff-panel");for(var i=0;i<ps.length;i++)ps[i].style.display=i==v?"block":"none";}</script>')
            metrics.append({"label": "远场文件数", "value": str(len(ff_files)), "css_class": ""})

        # 2D section
        two_d_files = sorted(exports_d.glob("result_2d_*.json"))
        if two_d_files:
            body_parts.append(f'<h2 class="section-h2">{_SECTION_LABELS["2d"]}</h2>')
            for td in two_d_files:
                try:
                    payload = _load_exported_payload(str(td))
                    svg = svg_heatmap(
                        x=payload.get("xpositions", []), y=payload.get("ypositions", []),
                        z=payload.get("data", []), title=payload.get("title", td.stem),
                        xlabel=payload.get("xlabel", "X"), ylabel=payload.get("ylabel", "Y"),
                        zlabel=payload.get("zlabel", "Value"),
                    )
                    body_parts.append(f'<div class="chart-panel">{svg}</div>')
                except Exception:
                    pass

        # Timeline / params section
        timeline = _build_timeline(str(dd))
        if timeline:
            body_parts.append(f'<h2 class="section-h2">{_SECTION_LABELS["timeline"]}（{len(timeline)} 步）</h2>')
            for idx, rec in enumerate(timeline, 1):
                body_parts.append(_step_card_html(idx, rec, s11_data))

            param_changes = [r for r in timeline if _categorize_step(r) == "param_change"]
            if param_changes:
                body_parts.append(f'<h2 class="section-h2">{_SECTION_LABELS["params"]}</h2>')
                body_parts.append(_param_changes_table_html(timeline))
                metrics.append({"label": "参数变更", "value": str(len(param_changes)), "css_class": ""})

        # Other field exports
        for suffix, label_key in [("efield_*.txt", "efield"), ("surface_current_*.txt", "surface_current"), ("voltage_*.txt", "voltage")]:
            files = sorted(exports_d.glob(suffix))
            if files:
                body_parts.append(f'<h2 class="section-h2">{_SECTION_LABELS[label_key]}（{len(files)} 文件）</h2>')
                body_parts.append(f'<table><thead><tr><th>文件</th></tr></thead><tbody>{"".join(f"<tr><td>{escape(f.name)}</td></tr>" for f in files)}</tbody></table>')

        body = "\n".join(body_parts)
        metrics_html_str = metric_cards_html(metrics) if metrics else ""
        target.write_text(
            svg_page(title, body, metrics_html=metrics_html_str,
                      subtitle=f"数据目录：{str(exports_d)}"),
            encoding="utf-8")

        return {
            "status": "success",
            "output_html": str(target),
            "s11_count": len(s11_data),
            "farfield_count": len(ff_files),
            "timeline_count": len(timeline),
            "runtime_module": "cst_runtime.render.dashboard",
        }
    except Exception as exc:
        return error_response(
            "generate_report_failed",
            str(exc),
            data_dir=str(data_dir),
            runtime_module="cst_runtime.render.dashboard",
        )