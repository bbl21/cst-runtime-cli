# -*- coding: utf-8 -*-
"""
CST 结果查询 MCP 服务
使用 cst.results 模块读取仿真结果，无需运行中的 CST 实例

使用方法：
1. 注册为单独的 MCP 服务
2. 使用 open_project 打开项目文件
3. 使用结果查询工具读取数据
4. 使用绘图工具生成接近 CST 内部查看体验的交互式 HTML 预览
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any


import cst.results
from mcp.server import FastMCP

mcp = FastMCP("cst_results_interface", log_level="ERROR")

_current_project_path: str | None = None
_current_active_subproject: str | None = None
_current_allow_interactive: bool = False
# 缓存：同一文件路径+子项目+interactive 模式下复用同一 ProjectFile 实例
_project_cache: dict[tuple[str, str | None, bool], cst.results.ProjectFile] = {}

DEFAULT_PLOT_DIR = Path(__file__).resolve().parent / "plot_previews"
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


def save_project_context(
    fullpath: str,
    allow_interactive: bool = False,
    subproject_treepath: str | None = None,
):
    """保存当前项目上下文"""
    global _current_project_path, _current_active_subproject, _current_allow_interactive
    _current_project_path = os.path.abspath(fullpath)
    _current_active_subproject = subproject_treepath
    _current_allow_interactive = allow_interactive


def get_project_context():
    """读取当前项目上下文"""
    global _current_project_path, _current_active_subproject, _current_allow_interactive
    if _current_project_path:
        return {
            "fullpath": _current_project_path,
            "active_subproject": _current_active_subproject,
            "allow_interactive": _current_allow_interactive,
        }
    return None


def clear_project_context():
    """清除当前项目上下文"""
    global _current_project_path, _current_active_subproject, _current_allow_interactive
    _current_project_path = None
    _current_active_subproject = None
    _current_allow_interactive = False


def _serialize_value(value: Any):
    """将 cst.results 返回值转换为可 JSON 序列化的数据"""
    if isinstance(value, complex):
        return {
            "real": value.real,
            "imag": value.imag,
            "complex_str": str(value),
        }
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if hasattr(value, "tolist"):
        return _serialize_value(value.tolist())
    return value


def _load_project():
    """按当前上下文重新加载 ProjectFile / 子项目

    关键：cst.interface.Project（modeler）和 cst.results.ProjectFile（results）
    是不同的 COM 对象，不能混用。必须各自独立创建。
    但多次调用 _load_project 加载同一文件时，缓存同一 ProjectFile 实例，
    复用会话，避免重复创建。
    """
    context = get_project_context()
    if not context:
        raise RuntimeError("当前没有活动的项目，请先调用 open_project")

    cache_key = (
        context["fullpath"],
        context.get("active_subproject"),
        context["allow_interactive"],
    )
    cached = _project_cache.get(cache_key)
    if cached is not None:
        return cached, context

    project = cst.results.ProjectFile(
        context["fullpath"],
        allow_interactive=context["allow_interactive"],
    )

    active_subproject = context.get("active_subproject")
    if active_subproject:
        project = project.load_subproject(active_subproject)

    _project_cache[cache_key] = project
    return project, context


def _get_result_module(project, module_type: str):
    module_key = (module_type or "3d").lower()
    if module_key == "schematic":
        return project.get_schematic(), "schematic"
    return project.get_3d(), "3d"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _ensure_plot_output_path(output_html: str = "", prefix: str = "plot") -> Path:
    if output_html:
        target = Path(output_html).expanduser()
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()
    else:
        DEFAULT_PLOT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = (DEFAULT_PLOT_DIR / f"{prefix}_{timestamp}.html").resolve()

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _is_complex_payload(value: Any) -> bool:
    return isinstance(value, dict) and "real" in value and "imag" in value


def _complex_components(value: Any) -> tuple[float, float]:
    if _is_complex_payload(value):
        return float(value.get("real", 0.0)), float(value.get("imag", 0.0))
    if isinstance(value, complex):
        return float(value.real), float(value.imag)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), 0.0
    return 0.0, 0.0


def _to_scalar(value: Any) -> float:
    if _is_complex_payload(value):
        real, imag = _complex_components(value)
        return math.sqrt(real * real + imag * imag)
    if isinstance(value, complex):
        return abs(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _phase_deg(value: Any) -> float:
    real, imag = _complex_components(value)
    return math.degrees(math.atan2(imag, real))


def _safe_log_db(value: float) -> float | None:
    if value <= 0:
        return None
    return 20.0 * math.log10(value)


def _first_numeric_column(rows: list[list[str]], col_index: int) -> list[float]:
    values: list[float] = []
    for row in rows:
        if col_index >= len(row):
            continue
        cell = row[col_index].strip()
        if cell == "":
            continue
        values.append(float(cell))
    return values


def _infer_xy_from_rows(rows: list[list[str]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("文件没有可解析的数据行")

    numeric_rows: list[list[float]] = []
    for row in rows:
        parsed_row: list[float] = []
        for cell in row:
            parsed_row.append(float(cell.strip()))
        numeric_rows.append(parsed_row)

    widths = {len(row) for row in numeric_rows}
    if len(widths) != 1:
        raise ValueError("文件列数不一致，无法自动绘图")

    width = widths.pop()
    if width == 1:
        return {
            "kind": "1d",
            "xdata": list(range(1, len(numeric_rows) + 1)),
            "ydata": [row[0] for row in numeric_rows],
            "title": "单列数值数据",
            "xlabel": "Index",
            "ylabel": "Value",
        }
    if width == 2:
        return {
            "kind": "1d",
            "xdata": [row[0] for row in numeric_rows],
            "ydata": [row[1] for row in numeric_rows],
            "title": "二维表格曲线",
            "xlabel": "X",
            "ylabel": "Y",
        }
    return {
        "kind": "2d",
        "xpositions": list(range(width)),
        "ypositions": list(range(len(numeric_rows))),
        "data": numeric_rows,
        "title": "矩阵热图",
        "xlabel": "Column",
        "ylabel": "Row",
        "dataunit": "",
    }


def _try_parse_cst_farfield_ascii(
    text: str, filename: str = ""
) -> dict[str, Any] | None:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    header_index = -1
    source_quantity = "Abs(E)"
    data_unit = "V/m"
    for idx, line in enumerate(lines[:10]):
        normalized = line.lower().replace(" ", "")
        if (
            "theta[deg.]" in normalized
            and "phi[deg.]" in normalized
            and ("abs(e" in normalized or "abs(gain)" in normalized)
        ):
            header_index = idx
            if "abs(gain)" in normalized:
                source_quantity = "Abs(Gain)"
                data_unit = ""
            break

    if header_index < 0:
        return None

    data_rows: list[list[float]] = []
    for line in lines[header_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        if set(stripped) <= {"-", "="}:
            continue
        parts = stripped.split()
        if len(parts) < 8:
            continue
        try:
            data_rows.append([float(parts[i]) for i in range(8)])
        except Exception:
            continue

    if not data_rows:
        raise ValueError("识别到 CST farfield ASCII 表头，但未解析出有效数据行")

    theta_values = sorted({row[0] for row in data_rows})
    phi_values = sorted({row[1] for row in data_rows})
    theta_index = {value: idx for idx, value in enumerate(theta_values)}
    phi_index = {value: idx for idx, value in enumerate(phi_values)}

    abs_e_matrix = [[None for _ in theta_values] for _ in phi_values]
    abs_theta_matrix = [[None for _ in theta_values] for _ in phi_values]
    phase_theta_matrix = [[None for _ in theta_values] for _ in phi_values]
    abs_phi_matrix = [[None for _ in theta_values] for _ in phi_values]
    phase_phi_matrix = [[None for _ in theta_values] for _ in phi_values]
    ax_ratio_matrix = [[None for _ in theta_values] for _ in phi_values]

    for row in data_rows:
        theta_idx = theta_index[row[0]]
        phi_idx = phi_index[row[1]]
        abs_e_matrix[phi_idx][theta_idx] = row[2]
        abs_theta_matrix[phi_idx][theta_idx] = row[3]
        phase_theta_matrix[phi_idx][theta_idx] = row[4]
        abs_phi_matrix[phi_idx][theta_idx] = row[5]
        phase_phi_matrix[phi_idx][theta_idx] = row[6]
        ax_ratio_matrix[phi_idx][theta_idx] = row[7]

    # 缝合：若 Phi 未到 360°，在末尾追加一行等于 Phi=0° 的数据，闭合极坐标圆
    if phi_values and phi_values[-1] < 360.0 - 1e-6:
        phi_values.append(360.0)
        phi_0_row = abs_e_matrix[0][:]
        abs_e_matrix.append(phi_0_row)
        abs_theta_matrix.append(abs_theta_matrix[0][:])
        phase_theta_matrix.append(phase_theta_matrix[0][:])
        abs_phi_matrix.append(abs_phi_matrix[0][:])
        phase_phi_matrix.append(phase_phi_matrix[0][:])
        ax_ratio_matrix.append(ax_ratio_matrix[0][:])

    def _fill_none(matrix: list[list[float | None]]) -> list[list[float]]:
        return [
            [0.0 if cell is None else float(cell) for cell in row] for row in matrix
        ]

    return {
        "kind": "2d",
        "title": f"CST Farfield ASCII - {filename or source_quantity}",
        "xlabel": "Theta [deg.]",
        "ylabel": "Phi [deg.]",
        "dataunit": data_unit,
        "xpositions": theta_values,
        "ypositions": phi_values,
        "data": _fill_none(abs_e_matrix),
        "meta": {
            "source_format": "cst_farfield_ascii",
            "source_quantity": source_quantity,
            "point_count": len(data_rows),
            "theta_count": len(theta_values),
            "phi_count": len(phi_values),
            "components": {
                "abs_theta": _fill_none(abs_theta_matrix),
                "phase_theta": _fill_none(phase_theta_matrix),
                "abs_phi": _fill_none(abs_phi_matrix),
                "phase_phi": _fill_none(phase_phi_matrix),
                "ax_ratio": _fill_none(ax_ratio_matrix),
            },
        },
    }


def _load_exported_payload(file_path: str) -> dict[str, Any]:
    target = Path(file_path)
    if not target.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    suffix = target.suffix.lower()
    if suffix == ".json":
        with target.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            raise ValueError(
                "JSON 文件内容必须是对象，且应包含 xdata/ydata 或二维 data"
            )
        return payload

    text = target.read_text(encoding="utf-8-sig")
    farfield_payload = _try_parse_cst_farfield_ascii(text, target.name)
    if farfield_payload is not None:
        farfield_payload.setdefault("meta", {})["source_file"] = str(target.resolve())
        return farfield_payload

    with target.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t; ")
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        rows = [row for row in reader if row and any(cell.strip() for cell in row)]

    if not rows:
        raise ValueError("文件为空或没有可解析内容")

    try:
        return _infer_xy_from_rows(rows)
    except Exception:
        try:
            return _infer_xy_from_rows(rows[1:])
        except Exception as e:
            raise ValueError(f"无法自动解析导出文件为可绘图数据: {str(e)}")


def _parse_frequency_from_name(name: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*GHz", name, flags=re.I)
    if match:
        return float(match.group(1))
    match = re.search(r"f\s*=\s*(\d+(?:\.\d+)?)", name, flags=re.I)
    if match:
        return float(match.group(1))
    return None


def _load_farfield_payloads(file_paths: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for file_path in file_paths:
        payload = _load_exported_payload(file_path)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        source_format = (meta.get("source_format") or "").strip().lower()
        if source_format != "cst_farfield_ascii":
            raise ValueError(f"仅支持 CST farfield ASCII 文件: {file_path}")

        source_file = meta.get("source_file") or str(Path(file_path).resolve())
        freq = _parse_frequency_from_name(Path(source_file).name)
        if freq is None:
            freq = _parse_frequency_from_name(str(Path(source_file).parent))

        matrix = _normalize_matrix(payload.get("data"))
        xpositions = payload.get("xpositions") or []
        ypositions = payload.get("ypositions") or []
        if not matrix or not xpositions or not ypositions:
            raise ValueError(f"远场文件缺少有效矩阵或坐标: {file_path}")

        max_value = max(cell for row in matrix for cell in row)
        norm_matrix = [
            [(cell / max_value) if max_value > 0 else 0.0 for cell in row]
            for row in matrix
        ]
        db_matrix = [
            [safe if (safe := _safe_log_db(v)) is not None else -120.0 for v in row]
            for row in norm_matrix
        ]

        def _cut_for_phi(target_phi: float):
            idx = min(
                range(len(ypositions)),
                key=lambda i: abs(float(ypositions[i]) - target_phi),
            )
            return {
                "phi": float(ypositions[idx]),
                "theta": [float(v) for v in xpositions],
                "gain_db": [float(v) for v in db_matrix[idx]],
            }

        items.append(
            {
                "label": f"{freq:g} GHz"
                if freq is not None
                else Path(source_file).stem,
                "frequency": freq,
                "file": str(Path(source_file)),
                "points": int(
                    meta.get("point_count", len(xpositions) * len(ypositions))
                ),
                "theta_range": [float(xpositions[0]), float(xpositions[-1])],
                "phi_range": [float(ypositions[0]), float(ypositions[-1])],
                "theta_step": float(xpositions[1] - xpositions[0])
                if len(xpositions) > 1
                else None,
                "phi_step": float(ypositions[1] - ypositions[0])
                if len(ypositions) > 1
                else None,
                "min_db": min(cell for row in db_matrix for cell in row),
                "max_db": max(cell for row in db_matrix for cell in row),
                "theta": [float(v) for v in xpositions],
                "phi": [float(v) for v in ypositions],
                "radius": norm_matrix,
                "surface_color": db_matrix,
                "cuts": [_cut_for_phi(0.0), _cut_for_phi(90.0)],
            }
        )

    items.sort(
        key=lambda x: (999999 if x["frequency"] is None else x["frequency"], x["label"])
    )
    return items


def _build_summary_cards(cards: list[tuple[str, Any]]) -> str:
    items = []
    for label, value in cards:
        items.append(
            f"<div class='card'><div class='label'>{label}</div><div class='value'>{value}</div></div>"
        )
    return "\n".join(items)


def _html_template(title: str, body: str, script: str) -> str:
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <script src=\"{PLOTLY_CDN}\"></script>
  <style>
    :root {{
      --bg: #111827;
      --panel: #1f2937;
      --panel-2: #0f172a;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --line: #334155;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); }}
    .wrap {{ max-width: 1600px; margin: 0 auto; padding: 20px; }}
    .header {{ margin-bottom: 18px; }}
    .title {{ font-size: 28px; font-weight: 700; margin-bottom: 6px; }}
    .subtitle {{ color: var(--muted); font-size: 14px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0 22px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px; min-height: 88px; }}
    .label {{ color: var(--muted); font-size: 12px; margin-bottom: 10px; }}
    .value {{ font-size: 22px; font-weight: 700; line-height: 1.2; word-break: break-word; }}
    .section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 16px; margin-bottom: 16px; }}
    .section h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .plot {{ width: 100%; height: 520px; }}
    .plot.small {{ height: 380px; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .note {{ color: var(--muted); font-size: 13px; margin-top: 6px; }}
    @media (max-width: 1100px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">{body}</div>
  <script>{script}</script>
</body>
</html>
"""


def _create_1d_plot_html(payload: dict[str, Any], page_title: str) -> str:
    xdata = payload.get("xdata", []) or []
    ydata = payload.get("ydata", []) or []
    xlabel = payload.get("xlabel", "X") or "X"
    ylabel = payload.get("ylabel", "Y") or "Y"
    title = payload.get("title", page_title) or page_title

    real_values = []
    imag_values = []
    mag_values = []
    phase_values = []
    has_complex = False
    for item in ydata:
        real, imag = _complex_components(item)
        mag = _to_scalar(item)
        real_values.append(real)
        imag_values.append(imag)
        mag_values.append(mag)
        phase_values.append(_phase_deg(item))
        if abs(imag) > 0:
            has_complex = True

    mag_db_values = [_safe_log_db(v) for v in mag_values]
    finite_mag_db = [v for v in mag_db_values if v is not None]
    point_count = len(xdata)

    cards = [
        ("数据类型", "1D/曲线" if point_count > 1 else "单点数据"),
        ("点数", point_count),
        ("X轴", xlabel),
        ("Y轴", ylabel),
    ]
    if xdata:
        cards.append(("起点", xdata[0]))
        cards.append(("终点", xdata[-1]))
    if mag_values:
        cards.append(("幅值最小", round(min(mag_values), 6)))
        cards.append(("幅值最大", round(max(mag_values), 6)))
    if finite_mag_db:
        cards.append(("幅值dB最小", round(min(finite_mag_db), 4)))
        cards.append(("幅值dB最大", round(max(finite_mag_db), 4)))

    body = f"""
    <div class=\"header\">
      <div class=\"title\">{title}</div>
      <div class=\"subtitle\">交互式结果预览 · 支持缩放、平移、悬停读取、导出图片</div>
    </div>
    <div class=\"cards\">{_build_summary_cards(cards)}</div>
    <div class=\"section\">
      <h2>主曲线预览</h2>
      <div id=\"plot_main\" class=\"plot\"></div>
      <div class=\"note\">复数结果默认以幅值显示；如存在虚部，下面还会给出相位与实虚部拆分。</div>
    </div>
    <div class=\"grid-2\">
      <div class=\"section\">
        <h2>幅值 dB</h2>
        <div id=\"plot_db\" class=\"plot small\"></div>
      </div>
      <div class=\"section\">
        <h2>相位 / 度</h2>
        <div id=\"plot_phase\" class=\"plot small\"></div>
      </div>
    </div>
    <div class=\"section\">
      <h2>实部 / 虚部</h2>
      <div id=\"plot_complex\" class=\"plot\"></div>
    </div>
    """

    title_json = _json_dumps(title)
    xlabel_json = _json_dumps(xlabel)
    ylabel_json = _json_dumps(ylabel)
    x_json = _json_dumps(xdata)
    mag_json = _json_dumps(mag_values)
    mag_db_json = _json_dumps(mag_db_values)
    phase_json = _json_dumps(phase_values)
    real_json = _json_dumps(real_values)
    imag_json = _json_dumps(imag_values)

    if point_count <= 1:
        main_trace_expr = "[{type:'indicator',mode:'number',value:mag[0] ?? 0,number:{font:{size:56}},title:{text:'单点幅值'}}]"
        main_layout_extra = "{margin:{t:40,r:30,b:30,l:30}}"
    else:
        main_trace_expr = "[{x:x,y:mag,type:'scatter',mode:'lines',name:'Magnitude',line:{color:'#38bdf8',width:2}}]"
        main_layout_extra = (
            "{xaxis:{title:xlabel},yaxis:{title:ylabel},hovermode:'x unified'}"
        )

    script = f"""
const x = {x_json};
const mag = {mag_json};
const magDb = {mag_db_json};
const phase = {phase_json};
const realPart = {real_json};
const imagPart = {imag_json};
const title = {title_json};
const xlabel = {xlabel_json};
const ylabel = {ylabel_json};
const template = 'plotly_dark';

Plotly.newPlot('plot_main', {main_trace_expr}, {{
  template,
  title: title,
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937',
  ...{main_layout_extra}
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_db', [{{
  x: x,
  y: magDb,
  type: 'scatter',
  mode: 'lines',
  name: 'Magnitude (dB)',
  line: {{color:'#f59e0b',width:2}}
}}], {{
  template,
  title: 'Magnitude (dB)',
  xaxis: {{title: xlabel}},
  yaxis: {{title: 'dB'}},
  hovermode: 'x unified',
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_phase', [{{
  x: x,
  y: phase,
  type: 'scatter',
  mode: 'lines',
  name: 'Phase',
  line: {{color:'#a78bfa',width:2}}
}}], {{
  template,
  title: 'Phase (deg)',
  xaxis: {{title: xlabel}},
  yaxis: {{title: 'deg'}},
  hovermode: 'x unified',
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_complex', [
  {{x:x,y:realPart,type:'scatter',mode:'lines',name:'Real',line:{{color:'#22c55e',width:2}}}},
  {{x:x,y:imagPart,type:'scatter',mode:'lines',name:'Imag',line:{{color:'#ef4444',width:2,dash:'dot'}}}}
], {{
  template,
  title: 'Real / Imag',
  xaxis: {{title: xlabel}},
  yaxis: {{title: hasComplex ? 'Component' : ylabel}},
  hovermode: 'x unified',
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});
""".replace("hasComplex", "true" if has_complex else "false")

    return _html_template(page_title, body, script)


def _normalize_matrix(data: Any) -> list[list[float]]:
    if not isinstance(data, list) or not data:
        raise ValueError("二维结果缺少有效 data 矩阵")

    matrix: list[list[float]] = []
    for row in data:
        if not isinstance(row, list):
            raise ValueError("二维结果矩阵格式无效")
        matrix.append([_to_scalar(cell) for cell in row])
    return matrix


def _create_2d_plot_html(payload: dict[str, Any], page_title: str) -> str:
    title = payload.get("title", page_title) or page_title
    xlabel = payload.get("xlabel", "X") or "X"
    ylabel = payload.get("ylabel", "Y") or "Y"
    xpositions = payload.get("xpositions") or []
    ypositions = payload.get("ypositions") or []
    matrix = _normalize_matrix(payload.get("data"))
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    source_format = (meta.get("source_format") or "").strip().lower()
    component_payload = (
        meta.get("components") if isinstance(meta.get("components"), dict) else {}
    )
    ny = len(matrix)
    nx = len(matrix[0]) if matrix else 0

    if not xpositions or len(xpositions) != nx:
        xpositions = list(range(nx))
    if not ypositions or len(ypositions) != ny:
        ypositions = list(range(ny))

    flat_values = [cell for row in matrix for cell in row]
    min_value = min(flat_values) if flat_values else 0.0
    max_value = max(flat_values) if flat_values else 0.0
    mid_row = matrix[ny // 2] if ny else []
    mid_col = [row[nx // 2] for row in matrix] if nx else []

    cards = [
        ("数据类型", "2D/多维切片"),
        ("尺寸", f"{ny} × {nx}"),
        ("X轴", xlabel),
        ("Y轴", ylabel),
        ("最小值", round(min_value, 6)),
        ("最大值", round(max_value, 6)),
        ("X范围", f"{xpositions[0]} ~ {xpositions[-1]}" if xpositions else "N/A"),
        ("Y范围", f"{ypositions[0]} ~ {ypositions[-1]}" if ypositions else "N/A"),
    ]
    if source_format == "cst_farfield_ascii":
        cards.extend(
            [
                ("源格式", "CST Farfield ASCII"),
                ("点数", meta.get("point_count", ny * nx)),
                ("Theta数", meta.get("theta_count", nx)),
                ("Phi数", meta.get("phi_count", ny)),
            ]
        )

    extra_sections = ""
    if source_format == "cst_farfield_ascii":
        extra_sections = """
    <div class="grid-2">
      <div class="section">
        <h2>Abs(Theta) 热图</h2>
        <div id="plot_abs_theta" class="plot small"></div>
      </div>
      <div class="section">
        <h2>Abs(Phi) 热图</h2>
        <div id="plot_abs_phi" class="plot small"></div>
      </div>
    </div>
    <div class="grid-2">
      <div class="section">
        <h2>Phase(Theta) 热图</h2>
        <div id="plot_phase_theta" class="plot small"></div>
      </div>
      <div class="section">
        <h2>Phase(Phi) 热图</h2>
        <div id="plot_phase_phi" class="plot small"></div>
      </div>
    </div>
    <div class="section">
      <h2>Axial Ratio 热图</h2>
      <div id="plot_ax_ratio" class="plot small"></div>
      <div class="note">对于四脊喇叭这类双极化结构，直接看 Abs(E) 可能会把两正交极化混合；建议配合 Abs(Theta)/Abs(Phi) 一起判断。</div>
    </div>
    """

    body = f"""
    <div class="header">
      <div class="title">{title}</div>
      <div class="subtitle">二维/多维结果可视化 · 热图、等值线、3D表面与中心切片预览</div>
    </div>
    <div class="cards">{_build_summary_cards(cards)}</div>
    <div class="grid-2">
      <div class="section">
        <h2>热图</h2>
        <div id="plot_heatmap" class="plot small"></div>
      </div>
      <div class="section">
        <h2>等值线 / 分析切片</h2>
        <div id="plot_contour" class="plot small"></div>
      </div>
    </div>
    <div class="section">
      <h2>3D 分析图预览</h2>
      <div id="plot_surface" class="plot"></div>
    </div>
    <div class="grid-2">
      <div class="section">
        <h2>中心横向切片</h2>
        <div id="plot_row_slice" class="plot small"></div>
      </div>
      <div class="section">
        <h2>中心纵向切片</h2>
        <div id="plot_col_slice" class="plot small"></div>
      </div>
    </div>
    {extra_sections}
    """

    title_json = _json_dumps(title)
    xlabel_json = _json_dumps(xlabel)
    ylabel_json = _json_dumps(ylabel)
    x_json = _json_dumps(xpositions)
    y_json = _json_dumps(ypositions)
    z_json = _json_dumps(matrix)
    row_slice_json = _json_dumps(mid_row)
    col_slice_json = _json_dumps(mid_col)
    abs_theta_json = _json_dumps(
        _normalize_matrix(component_payload.get("abs_theta"))
        if component_payload.get("abs_theta")
        else []
    )
    abs_phi_json = _json_dumps(
        _normalize_matrix(component_payload.get("abs_phi"))
        if component_payload.get("abs_phi")
        else []
    )
    phase_theta_json = _json_dumps(
        _normalize_matrix(component_payload.get("phase_theta"))
        if component_payload.get("phase_theta")
        else []
    )
    phase_phi_json = _json_dumps(
        _normalize_matrix(component_payload.get("phase_phi"))
        if component_payload.get("phase_phi")
        else []
    )
    ax_ratio_json = _json_dumps(
        _normalize_matrix(component_payload.get("ax_ratio"))
        if component_payload.get("ax_ratio")
        else []
    )
    source_format_json = _json_dumps(source_format)

    script = f"""
const x = {x_json};
const y = {y_json};
const z = {z_json};
const midRow = {row_slice_json};
const midCol = {col_slice_json};
const title = {title_json};
const xlabel = {xlabel_json};
const ylabel = {ylabel_json};
const sourceFormat = {source_format_json};
const absThetaMatrix = {abs_theta_json};
const absPhiMatrix = {abs_phi_json};
const phaseThetaMatrix = {phase_theta_json};
const phasePhiMatrix = {phase_phi_json};
const axRatioMatrix = {ax_ratio_json};
const template = 'plotly_dark';

function safeDb(v) {{
  return v > 0 ? 20 * Math.log10(v) : -120;
}}

function buildFarfieldCartesian(thetaDeg, phiDeg, radiusMatrix) {{
  const xs = [];
  const ys = [];
  const zs = [];
  for (let i = 0; i < phiDeg.length; i++) {{
    const xr = [];
    const yr = [];
    const zr = [];
    for (let j = 0; j < thetaDeg.length; j++) {{
      const theta = thetaDeg[j] * Math.PI / 180.0;
      const phi = phiDeg[i] * Math.PI / 180.0;
      const r = radiusMatrix[i][j];
      xr.push(r * Math.sin(theta) * Math.cos(phi));
      yr.push(r * Math.sin(theta) * Math.sin(phi));
      zr.push(r * Math.cos(theta));
    }}
    xs.push(xr);
    ys.push(yr);
    zs.push(zr);
  }}
  return {{x: xs, y: ys, z: zs}};
}}

Plotly.newPlot('plot_heatmap', [{{
  x: x,
  y: y,
  z: z,
  type: 'heatmap',
  colorscale: 'Jet',
  colorbar: {chr(123)}title: 'Value'{chr(125)}
}}], {{
  template,
  title: title + ' · Heatmap',
  xaxis: {{title: xlabel}},
  yaxis: {{title: ylabel}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_contour', [{{
  x: x,
  y: y,
  z: z,
  type: 'contour',
  colorscale: 'Jet',
  contours: {{coloring:'heatmap'}},
  colorbar: {chr(123)}title: 'Value'{chr(125)}
}}], {{
  template,
  title: title + ' · Contour',
  xaxis: {{title: xlabel}},
  yaxis: {{title: ylabel}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

if (sourceFormat === 'cst_farfield_ascii') {{
  let maxVal = 0;
  for (const row of z) {{
    for (const v of row) {{
      if (v > maxVal) maxVal = v;
    }}
  }}
  const radius = z.map(row => row.map(v => maxVal > 0 ? v / maxVal : 0));
  const colorDb = z.map(row => row.map(v => safeDb(maxVal > 0 ? v / maxVal : 0)));
  const ff = buildFarfieldCartesian(x, y, radius);
  Plotly.newPlot('plot_surface', [{{
    x: ff.x,
    y: ff.y,
    z: ff.z,
    surfacecolor: colorDb,
    type: 'surface',
    colorscale: 'Jet',
    cmin: -40,
    cmax: 0,
    colorbar: {chr(123)}title: 'Norm dB'{chr(125)}
  }}], {{
    template,
    title: title + ' · 3D Polar Farfield',
    scene: {{
      xaxis: {{title: 'X'}},
      yaxis: {{title: 'Y'}},
      zaxis: {{title: 'Z'}},
      aspectmode: 'data',
      camera: {{eye: {{x: 1.7, y: 1.6, z: 1.1}}}}
    }},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}} else {{
  Plotly.newPlot('plot_surface', [{{
    x: x,
    y: y,
    z: z,
    type: 'surface',
    colorscale: 'Jet',
    colorbar: {chr(123)}title: 'Value'{chr(125)}
  }}], {{
    template,
    title: title + ' · 3D Surface Preview',
    scene: {{
      xaxis: {{title: xlabel}},
      yaxis: {{title: ylabel}},
      zaxis: {{title: 'Value'}},
      camera: {{eye: {{x: 1.7, y: 1.6, z: 1.1}}}}
    }},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}


Plotly.newPlot('plot_row_slice', [{{
  x: x,
  y: midRow,
  type: 'scatter',
  mode: 'lines',
  line: {{color:'#38bdf8',width:2}},
  name: 'Mid Row'
}}], {{
  template,
  title: '中心横向切片',
  xaxis: {{title: xlabel}},
  yaxis: {{title: 'Value'}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

Plotly.newPlot('plot_col_slice', [{{
  x: y,
  y: midCol,
  type: 'scatter',
  mode: 'lines',
  line: {{color:'#f97316',width:2}},
  name: 'Mid Column'
}}], {{
  template,
  title: '中心纵向切片',
  xaxis: {{title: ylabel}},
  yaxis: {{title: 'Value'}},
  paper_bgcolor:'#1f2937',
  plot_bgcolor:'#1f2937'
}}, {{responsive:true,displaylogo:false}});

if (sourceFormat === 'cst_farfield_ascii') {{
  Plotly.newPlot('plot_abs_theta', [{{x:x,y:y,z:absThetaMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'Abs(Theta)'{chr(125)}}}], {{template, title:'Abs(Theta)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_abs_phi', [{{x:x,y:y,z:absPhiMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'Abs(Phi)'{chr(125)}}}], {{template, title:'Abs(Phi)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_phase_theta', [{{x:x,y:y,z:phaseThetaMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'deg'{chr(125)}}}], {{template, title:'Phase(Theta)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_phase_phi', [{{x:x,y:y,z:phasePhiMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'deg'{chr(125)}}}], {{template, title:'Phase(Phi)', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
  Plotly.newPlot('plot_ax_ratio', [{{x:x,y:y,z:axRatioMatrix,type:'heatmap',colorscale:'Jet',colorbar:{chr(123)}title:'Ax.Ratio'{chr(125)}}}], {{template, title:'Axial Ratio', xaxis:{{title:xlabel}}, yaxis:{{title:ylabel}}, paper_bgcolor:'#1f2937', plot_bgcolor:'#1f2937'}}, {{responsive:true,displaylogo:false}});
}}
"""

    return _html_template(page_title, body, script)


def _create_farfield_multi_plot_html(
    items: list[dict[str, Any]], page_title: str
) -> str:
    if not items:
        raise ValueError("没有可用的远场文件")

    global_min_db = min(float(item["min_db"]) for item in items)
    global_max_db = max(float(item["max_db"]) for item in items)
    freqs = [item["frequency"] for item in items if item.get("frequency") is not None]
    summary_cards = [
        ("频率文件数", len(items)),
        ("频率范围", f"{min(freqs)} ~ {max(freqs)} GHz" if freqs else "N/A"),
        ("全局色标范围", f"{round(global_min_db, 2)} ~ {round(global_max_db, 2)} dB"),
        ("已载入频率", ", ".join(str(item["label"]) for item in items)),
    ]

    body = f"""
    <div class="header">
      <div class="title">{page_title}</div>
      <div class="subtitle">多频率远场方向图预览 · 单频 3D 图、单频主平面切面，以及跨频率对比曲线。Phi 末端已自动补 360°，保证 355° 与 0° 闭合。</div>
    </div>
    <div class="cards">{_build_summary_cards(summary_cards)}</div>
    <div class="section">
      <h2>选择单频查看</h2>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
        <select id="freqSelect" style="background:#0f172a;color:#e5e7eb;border:1px solid #334155;border-radius:10px;padding:10px 12px;min-width:220px;"></select>
        <div id="fileHint" class="note"></div>
      </div>
    </div>
    <div class="cards" id="singleCards"></div>
    <div class="section">
      <h2>单频 3D 方向图</h2>
      <div id="plot_surface3d" class="plot"></div>
    </div>
    <div class="grid-2">
      <div class="section">
        <h2>单频主平面切面（Phi = 0° / 90°）</h2>
        <div id="plot_single_cuts" class="plot small"></div>
      </div>
      <div class="section">
        <h2>说明</h2>
        <div class="note">该页面面向多个 farfield ASCII 文件联合展示。若继续导出 `farfield_8GHz.txt`、`farfield_12GHz.txt` 等文件，可直接再次调用本工具生成新的对比页。</div>
      </div>
    </div>
    <div class="section">
      <h2>多频率对比：Phi = 0°</h2>
      <div id="plot_compare_phi0" class="plot small"></div>
    </div>
    <div class="section">
      <h2>多频率对比：Phi = 90°</h2>
      <div id="plot_compare_phi90" class="plot small"></div>
    </div>
    """

    items_json = _json_dumps(items)
    title_json = _json_dumps(page_title)
    summary_json = _json_dumps(
        {"global_min_db": global_min_db, "global_max_db": global_max_db}
    )
    script = f"""
const items = {items_json};
const pageTitle = {title_json};
const summary = {summary_json};
const select = document.getElementById('freqSelect');
const fileHint = document.getElementById('fileHint');
const singleCards = document.getElementById('singleCards');
const palette = ['#38bdf8','#f59e0b','#ef4444','#22c55e','#a78bfa','#f472b6','#14b8a6','#eab308'];

function buildFarfieldCartesian(thetaDeg, phiDeg, radiusMatrix) {{
  const xs = [];
  const ys = [];
  const zs = [];
  for (let i = 0; i < phiDeg.length; i++) {{
    const xr = [];
    const yr = [];
    const zr = [];
    for (let j = 0; j < thetaDeg.length; j++) {{
      const theta = thetaDeg[j] * Math.PI / 180.0;
      const phi = phiDeg[i] * Math.PI / 180.0;
      const r = radiusMatrix[i][j];
      xr.push(r * Math.sin(theta) * Math.cos(phi));
      yr.push(r * Math.sin(theta) * Math.sin(phi));
      zr.push(r * Math.cos(theta));
    }}
    xs.push(xr);
    ys.push(yr);
    zs.push(zr);
  }}
  return {{x: xs, y: ys, z: zs}};
}}

items.forEach((item, idx) => {{
  const opt = document.createElement('option');
  opt.value = String(idx);
  opt.textContent = item.label;
  select.appendChild(opt);
}});

function renderSingleCards(item) {{
  singleCards.innerHTML = `
    <div class="card"><div class="label">频率</div><div class="value">${{item.label}}</div></div>
    <div class="card"><div class="label">数据点数</div><div class="value">${{item.points}}</div></div>
    <div class="card"><div class="label">Theta 范围</div><div class="value">${{item.theta_range[0]}} ~ ${{item.theta_range[1]}}°</div></div>
    <div class="card"><div class="label">Phi 范围</div><div class="value">${{item.phi_range[0]}} ~ ${{item.phi_range[1]}}°</div></div>
    <div class="card"><div class="label">单频动态范围</div><div class="value">${{item.min_db.toFixed(2)}} ~ ${{item.max_db.toFixed(2)}} dB</div></div>
    <div class="card"><div class="label">角步长</div><div class="value">θ ${{item.theta_step ?? '-'}}° / φ ${{item.phi_step ?? '-'}}°</div></div>
  `;
}}

function renderSingle3D(item) {{
  const ff = buildFarfieldCartesian(item.theta, item.phi, item.radius);
  Plotly.newPlot('plot_surface3d', [{{
    x: ff.x,
    y: ff.y,
    z: ff.z,
    surfacecolor: item.surface_color,
    type: 'surface',
    colorscale: 'Jet',
    cmin: summary.global_min_db,
    cmax: summary.global_max_db,
    colorbar: {chr(123)}title: 'Norm dB'{chr(125)}
  }}], {{
    template: 'plotly_dark',
    title: `${{item.label}} · 3D Polar Farfield`,
    scene: {{
      xaxis: {{title: 'X'}},
      yaxis: {{title: 'Y'}},
      zaxis: {{title: 'Z'}},
      aspectmode: 'data',
      camera: {{eye: {{x: 1.7, y: 1.6, z: 1.1}}}}
    }},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}

function renderSingleCuts(item) {{
  const traces = item.cuts.map((cut, idx) => ({{
    x: cut.theta,
    y: cut.gain_db,
    type: 'scatter',
    mode: 'lines',
    name: `Phi=${{cut.phi}}°`,
    line: {{width: 2.5, color: idx === 0 ? '#38bdf8' : '#f59e0b'}}
  }}));
  Plotly.newPlot('plot_single_cuts', traces, {{
    template: 'plotly_dark',
    title: `${{item.label}} · 主平面切面`,
    xaxis: {{title: 'Theta (deg)'}},
    yaxis: {{title: 'Normalized Gain (dB)'}},
    hovermode: 'x unified',
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}

function renderComparison(targetId, cutIndex, title) {{
  const traces = items.map((item, idx) => {{
    const cut = item.cuts[cutIndex];
    return {{
      x: cut.theta,
      y: cut.gain_db,
      type: 'scatter',
      mode: 'lines',
      name: `${{item.label}} (Phi=${{cut.phi}}°)`,
      line: {{width: 2.5, color: palette[idx % palette.length]}}
    }};
  }});
  Plotly.newPlot(targetId, traces, {{
    template: 'plotly_dark',
    title,
    xaxis: {{title: 'Theta (deg)'}},
    yaxis: {{title: 'Normalized Gain (dB)'}},
    hovermode: 'x unified',
    legend: {{orientation: 'h', y: 1.15}},
    paper_bgcolor:'#1f2937',
    plot_bgcolor:'#1f2937'
  }}, {{responsive:true,displaylogo:false}});
}}

function render(index) {{
  const item = items[index];
  fileHint.textContent = '源文件：' + item.file;
  renderSingleCards(item);
  renderSingle3D(item);
  renderSingleCuts(item);
}}

select.addEventListener('change', e => render(Number(e.target.value)));
render(0);
renderComparison('plot_compare_phi0', 0, pageTitle + ' · 多频率对比（目标 Phi = 0°）');
renderComparison('plot_compare_phi90', 1, pageTitle + ' · 多频率对比（目标 Phi = 90°）');
"""
    return _html_template(page_title, body, script)


def _build_plot_html_from_payload(
    payload: dict[str, Any], page_title: str
) -> tuple[str, str]:
    kind = (payload.get("kind") or "").lower().strip()

    if not kind:
        if "xdata" in payload and "ydata" in payload:
            kind = "1d"
        elif "data" in payload and isinstance(payload.get("data"), list):
            kind = "2d"

    if kind == "1d":
        return _create_1d_plot_html(payload, page_title), "1d"
    if kind == "2d":
        return _create_2d_plot_html(payload, page_title), "2d"

    raise ValueError("无法自动识别数据类型，请提供包含 xdata/ydata 或二维 data 的数据")


def _fetch_plot_payload_from_project(
    treepath: str, module_type: str, run_id: int, load_impedances: bool
):
    project, context = _load_project()
    result_module, normalized_module = _get_result_module(project, module_type)

    try:
        result_item = result_module.get_result_item(
            treepath,
            run_id=run_id,
            load_impedances=load_impedances,
        )
        payload = {
            "kind": "1d",
            "title": result_item.title,
            "xlabel": result_item.xlabel,
            "ylabel": result_item.ylabel,
            "xdata": _serialize_value(result_item.get_xdata()),
            "ydata": _serialize_value(result_item.get_ydata()),
            "run_id": result_item.run_id,
            "parameter_combination": _serialize_value(
                result_item.get_parameter_combination()
            ),
        }
        return payload, "1d", normalized_module, context
    except Exception as first_error:
        try:
            result_2d = result_module.get_result2d_item(treepath)
            payload = {
                "kind": "2d",
                "title": result_2d.title,
                "xlabel": result_2d.xlabel,
                "ylabel": result_2d.ylabel,
                "xunit": result_2d.xunit,
                "yunit": result_2d.yunit,
                "dataunit": result_2d.dataunit,
                "xpositions": _serialize_value(result_2d.get_xpositions()),
                "ypositions": _serialize_value(result_2d.get_ypositions()),
                "data": _serialize_value(result_2d.get_data()),
                "nx": result_2d.nx,
                "ny": result_2d.ny,
            }
            return payload, "2d", normalized_module, context
        except Exception as second_error:
            raise RuntimeError(
                f"无法将 treepath 识别为 1D 或 2D 结果。1D错误: {str(first_error)}；2D错误: {str(second_error)}"
            )


@mcp.tool()
def get_version_info():
    """获取 cst.results 模块版本信息

    返回 cst.results 相关文件的版本信息字典，便于排查接口兼容性。
    """
    try:
        return {
            "status": "success",
            "version_info": _serialize_value(cst.results.get_version_info()),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取版本信息失败: {str(e)}"}


@mcp.tool()
def open_project(fullpath: str, allow_interactive: bool = False):
    """打开 CST 项目文件（用于结果查询）

    使用 cst.results.ProjectFile 打开项目文件并保存上下文。
    allow_interactive=True 时可读取正在 CST 中打开且已保存的项目，但性能较低，
    且未保存状态下数据可能过时或不完整。

    参数:
    - fullpath: 项目文件完整路径
    - allow_interactive: 是否允许交互模式打开，默认 False

    返回:
    - status: 操作状态
    - fullpath: 项目路径
    - filename: 项目文件名
    - active_subproject: 当前活动子项目（初始为 null）
    """
    if not os.path.exists(fullpath):
        return {"status": "error", "message": f"项目文件不存在: {fullpath}"}

    try:
        abs_path = os.path.abspath(fullpath)
        project = cst.results.ProjectFile(abs_path, allow_interactive=allow_interactive)
        save_project_context(
            abs_path, allow_interactive=allow_interactive, subproject_treepath=None
        )
        return {
            "status": "success",
            "fullpath": abs_path,
            "filename": project.filename,
            "allow_interactive": allow_interactive,
            "active_subproject": None,
        }
    except Exception as e:
        return {"status": "error", "message": f"打开项目失败: {str(e)}"}


@mcp.tool()
def close_project():
    """关闭当前项目上下文"""
    global _project_cache
    context = get_project_context()
    if context:
        cache_key = (
            context["fullpath"],
            context.get("active_subproject"),
            context["allow_interactive"],
        )
        _project_cache.pop(cache_key, None)
    clear_project_context()
    return {"status": "success", "message": "项目已关闭"}


@mcp.tool()
def get_project_context_info():
    """获取当前项目上下文信息

    返回当前已打开项目路径、交互模式、当前活动子项目等信息。
    """
    context = get_project_context()
    if not context:
        return {"status": "error", "message": "当前没有活动的项目"}
    return {"status": "success", **context}


@mcp.tool()
def list_subprojects():
    """列出项目中的子项目

    列出 Schematic 中可通过 load_subproject 打开的子项目路径。
    """
    try:
        project, context = _load_project()
        subprojects = project.list_subprojects()
        return {
            "status": "success",
            "fullpath": context["fullpath"],
            "count": len(subprojects),
            "subprojects": subprojects,
        }
    except Exception as e:
        return {"status": "error", "message": f"获取子项目列表失败: {str(e)}"}


@mcp.tool()
def load_subproject(treepath: str):
    """切换当前活动子项目

    参数:
    - treepath: 子项目树路径，可先用 list_subprojects 获取

    返回:
    - status: 操作状态
    - active_subproject: 当前已切换到的子项目路径
    """
    context = get_project_context()
    if not context:
        return {
            "status": "error",
            "message": "当前没有活动的项目，请先调用 open_project",
        }

    try:
        root_project = cst.results.ProjectFile(
            context["fullpath"],
            allow_interactive=context["allow_interactive"],
        )
        subproject = root_project.load_subproject(treepath)
        save_project_context(
            context["fullpath"],
            allow_interactive=context["allow_interactive"],
            subproject_treepath=treepath,
        )
        return {
            "status": "success",
            "fullpath": context["fullpath"],
            "active_subproject": treepath,
            "filename": subproject.filename,
        }
    except Exception as e:
        return {"status": "error", "message": f"加载子项目失败: {str(e)}"}


@mcp.tool()
def reset_to_root_project():
    """从当前子项目切回根项目"""
    context = get_project_context()
    if not context:
        return {"status": "error", "message": "当前没有活动的项目"}

    save_project_context(
        context["fullpath"],
        allow_interactive=context["allow_interactive"],
        subproject_treepath=None,
    )
    return {
        "status": "success",
        "fullpath": context["fullpath"],
        "active_subproject": None,
        "message": "已切换回根项目",
    }


@mcp.tool()
def list_result_items(module_type: str = "3d", filter_type: str = "0D/1D"):
    """列出项目中的结果树项目

    参数:
    - module_type: 模块类型，"3d" 或 "schematic"，默认 "3d"
    - filter_type: 过滤类型，支持 "0D/1D"、"colormap"、"all"，默认 "0D/1D"

    说明:
    - `all` 会基于 cst.results 的 `_get_all_result_items()` 汇总所有可见结果项，
      可用于补充查看与 `0D/1D Results` 并列的结果分类。
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)

        normalized_filter = (filter_type or "0D/1D").strip()
        if normalized_filter.lower() == "all":
            all_items = result_module._get_all_result_items()
            treepaths = []
            seen = set()
            for item in all_items:
                treepath = getattr(item, "treepath", None)
                if not treepath or treepath in seen:
                    continue
                seen.add(treepath)
                treepaths.append(treepath)
            items = treepaths
        else:
            items = result_module.get_tree_items(filter=normalized_filter)

        return {
            "status": "success",
            "module_type": normalized_module,
            "filter_type": normalized_filter,
            "active_subproject": context["active_subproject"],
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        return {"status": "error", "message": f"查询结果树项目失败: {str(e)}"}


@mcp.tool()
def list_run_ids(
    treepath: str = "",
    module_type: str = "3d",
    skip_nonparametric: bool = False,
    max_mesh_passes_only: bool = True,
):
    """获取运行 ID 列表

    参数:
    - treepath: 结果树路径；为空时调用 get_all_run_ids
    - module_type: 模块类型，"3d" 或 "schematic"
    - skip_nonparametric: treepath 模式下是否跳过 run_id=0
    - max_mesh_passes_only: 全局模式下是否仅返回最高网格通过次数结果
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)

        treepath = treepath or ""
        if treepath:
            run_ids = result_module.get_run_ids(
                treepath, skip_nonparametric=skip_nonparametric
            )
        else:
            run_ids = result_module.get_all_run_ids(
                max_mesh_passes_only=max_mesh_passes_only
            )

        return {
            "status": "success",
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": treepath if treepath else None,
            "count": len(run_ids),
            "run_ids": _serialize_value(run_ids),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取运行 ID 列表失败: {str(e)}"}


@mcp.tool()
def get_parameter_combination(run_id: int, module_type: str = "3d"):
    """获取指定运行 ID 对应的参数组合"""
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)
        params = result_module.get_parameter_combination(run_id)
        return {
            "status": "success",
            "run_id": run_id,
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "parameters": _serialize_value(params),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取参数组合失败: {str(e)}"}


@mcp.tool()
def get_1d_result(
    treepath: str,
    module_type: str = "3d",
    run_id: int = 0,
    load_impedances: bool = True,
):
    """获取 0D/1D 结果数据

    对应 cst.results.ResultModule.get_result_item(treepath, run_id, load_impedances)。
    兼容 0D 结果、普通 1D 结果和带参考阻抗的结果。
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)
        result_item = result_module.get_result_item(
            treepath,
            run_id=run_id,
            load_impedances=load_impedances,
        )

        xdata = result_item.get_xdata()
        ydata = result_item.get_ydata()
        data = result_item.get_data()
        ref_imp_data = None
        try:
            ref_imp_data = result_item.get_ref_imp_data()
        except Exception:
            ref_imp_data = None

        return {
            "status": "success",
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": result_item.treepath,
            "title": result_item.title,
            "xlabel": result_item.xlabel,
            "ylabel": result_item.ylabel,
            "length": result_item.length,
            "run_id": result_item.run_id,
            "parameter_combination": _serialize_value(
                result_item.get_parameter_combination()
            ),
            "xdata": _serialize_value(xdata),
            "ydata": _serialize_value(ydata),
            "data": _serialize_value(data),
            "ref_impedance_data": _serialize_value(ref_imp_data),
        }
    except Exception as e:
        return {"status": "error", "message": f"获取 0D/1D 结果失败: {str(e)}"}


@mcp.tool()
def get_2d_result(treepath: str, module_type: str = "3d", include_data: bool = False):
    """获取 2D 结果数据（colormap）

    参数:
    - treepath: 结果树路径
    - module_type: 模块类型，"3d" 或 "schematic"
    - include_data: 是否返回完整二维数据；默认 False，仅返回元数据和尺寸
    """
    try:
        project, context = _load_project()
        result_module, normalized_module = _get_result_module(project, module_type)
        result_2d = result_module.get_result2d_item(treepath)

        response = {
            "status": "success",
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
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
            "include_data": include_data,
        }

        if include_data:
            response["data"] = _serialize_value(result_2d.get_data())
        else:
            response["data_preview"] = f"数据形状: {result_2d.ny} x {result_2d.nx}"

        return response
    except Exception as e:
        return {"status": "error", "message": f"获取 2D 结果失败: {str(e)}"}


@mcp.tool()
def plot_project_result(
    treepath: str,
    module_type: str = "3d",
    run_id: int = 0,
    load_impedances: bool = True,
    output_html: str = "",
    page_title: str = "",
):
    """从当前项目直接生成结果预览 HTML

    功能：
    - 自动识别 treepath 是 1D 结果还是 2D 结果
    - 1D 结果生成单点/曲线/实部虚部/幅值dB/相位图
    - 2D 结果生成热图、等值线、中心切片和 3D 表面预览
    - 输出交互式 HTML，便于在 WorkBuddy / 浏览器中查看

    参数：
    - treepath: 结果树路径
    - module_type: "3d" 或 "schematic"
    - run_id: 1D 结果所用 run id，默认 0
    - load_impedances: 1D 结果是否附带参考阻抗
    - output_html: 输出 HTML 文件路径；为空则自动写入 plot_previews 目录
    - page_title: 页面标题；为空则自动使用结果标题
    """
    try:
        payload, detected_kind, normalized_module, context = (
            _fetch_plot_payload_from_project(
                treepath=treepath,
                module_type=module_type,
                run_id=run_id,
                load_impedances=load_impedances,
            )
        )
        final_title = (
            page_title or payload.get("title") or f"CST Result Preview - {treepath}"
        )
        html_content, rendered_kind = _build_plot_html_from_payload(
            payload, final_title
        )
        target = _ensure_plot_output_path(output_html, prefix="project_result")
        target.write_text(html_content, encoding="utf-8")

        return {
            "status": "success",
            "source": "project_result",
            "detected_kind": detected_kind,
            "rendered_kind": rendered_kind,
            "module_type": normalized_module,
            "active_subproject": context["active_subproject"],
            "treepath": treepath,
            "run_id": run_id,
            "page_title": final_title,
            "output_html": str(target),
        }
    except Exception as e:
        return {"status": "error", "message": f"生成项目结果预览失败: {str(e)}"}


@mcp.tool()
def plot_exported_file(file_path: str, output_html: str = "", page_title: str = ""):
    """将导出的结果文件渲染为交互式 HTML 预览

    支持场景：
    - 导出的 CSV / TXT 两列曲线文件
    - 导出的矩阵型文本文件（按规则自动识别为热图）
    - 已整理成 JSON 的 xdata/ydata 或二维 data 数据

    参数：
    - file_path: 导出文件路径
    - output_html: 输出 HTML 文件路径；为空则自动写入 plot_previews 目录
    - page_title: 页面标题；为空则自动使用文件名或数据标题
    """
    try:
        payload = _load_exported_payload(file_path)
        payload_title = payload.get("title") if isinstance(payload, dict) else None
        final_title = (
            page_title or payload_title or f"Export Preview - {Path(file_path).name}"
        )
        html_content, rendered_kind = _build_plot_html_from_payload(
            payload, final_title
        )
        target = _ensure_plot_output_path(output_html, prefix="export_preview")
        target.write_text(html_content, encoding="utf-8")

        return {
            "status": "success",
            "source": "exported_file",
            "file_path": str(Path(file_path).resolve()),
            "rendered_kind": rendered_kind,
            "page_title": final_title,
            "output_html": str(target),
        }
    except Exception as e:
        return {"status": "error", "message": f"生成导出文件预览失败: {str(e)}"}


@mcp.tool()
def plot_farfield_multi(
    file_paths: list[str], output_html: str = "", page_title: str = ""
):
    """将多个 CST farfield ASCII 导出文件渲染为多频率交互式 HTML 预览

    参数：
    - file_paths: 多个 farfield ASCII 文件路径列表
    - output_html: 输出 HTML 文件路径；为空则自动写入 plot_previews 目录
    - page_title: 页面标题；为空则默认使用“Farfield Multi-Frequency Preview"
    """
    try:
        if not file_paths:
            raise ValueError("file_paths 不能为空")
        items = _load_farfield_payloads(file_paths)
        final_title = page_title or "Farfield Multi-Frequency Preview"
        html_content = _create_farfield_multi_plot_html(items, final_title)
        target = _ensure_plot_output_path(output_html, prefix="farfield_multi")
        target.write_text(html_content, encoding="utf-8")
        return {
            "status": "success",
            "source": "farfield_multi",
            "file_count": len(items),
            "file_paths": [str(Path(p).resolve()) for p in file_paths],
            "page_title": final_title,
            "output_html": str(target),
        }
    except Exception as e:
        return {"status": "error", "message": f"生成多频率远场预览失败: {str(e)}"}


if __name__ == "__main__":
    print("[MCP] cst_results_mcp: starting", flush=True)
    mcp.run(transport="stdio")
