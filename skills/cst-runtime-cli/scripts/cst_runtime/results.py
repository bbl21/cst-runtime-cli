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
_COLORS = ["#0d9488", "#d97706", "#7c3aed", "#dc2626", "#059669", "#0891b2", "#be185d", "#65a30d"]
_DARK_BG = "#18181b"
_DARK_TEXT = "#f4f4f5"
_LIGHT_BG = "#ffffff"
_LIGHT_TEXT = "#18181b"


def _svg_axes(x_min: float, x_max: float, y_min: float, y_max: float, xlabel: str, ylabel: str, dark: bool) -> str:
    m = _SVG_MARGIN
    pw = _SVG_W - m["l"] - m["r"]
    ph = _SVG_H - m["t"] - m["b"]
    bg = _DARK_BG if dark else _LIGHT_BG
    tc = _DARK_TEXT if dark else _LIGHT_TEXT
    gc = "#3f3f46" if dark else "#e4e4e7"
    ac = "#71717a" if dark else "#a1a1aa"

    x_pad = (x_max - x_min) * 0.03 or 1
    y_pad = (y_max - y_min) * 0.05 or 1
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def sx(v: float) -> float: return m["l"] + (v - x_min) / (x_max - x_min) * pw
    def sy(v: float) -> float: return m["t"] + ph - (v - y_min) / (y_max - y_min) * ph

    lines = [f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" fill="{bg}" rx="6"/>']
    lines.append(f'<g fill="{tc}" font-family="system-ui,-apple-system,sans-serif" font-size="14" font-weight="600">')
    lines.append(f'<text x="{_SVG_W/2}" y="24" text-anchor="middle" font-size="15">{escape(xlabel)} vs {escape(ylabel)}</text>')
    lines.append("</g>")

    # Grid + Y axis labels
    y_steps = 5
    for i in range(y_steps + 1):
        v = y_min + (y_max - y_min) * i / y_steps
        yy = sy(v)
        lines.append(f'<line x1="{m["l"]}" y1="{yy}" x2="{m["l"]+pw}" y2="{yy}" stroke="{gc}" stroke-width="0.5" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{m["l"]-8}" y="{yy+4}" text-anchor="end" fill="{ac}" font-family="system-ui,-apple-system,sans-serif" font-size="11">{v:.2f}</text>')
    # Grid + X axis labels
    x_steps = 8
    for i in range(x_steps + 1):
        v = x_min + (x_max - x_min) * i / x_steps
        xx = sx(v)
        lines.append(f'<line x1="{xx}" y1="{m["t"]}" x2="{xx}" y2="{m["t"]+ph}" stroke="{gc}" stroke-width="0.5" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{xx}" y="{m["t"]+ph+16}" text-anchor="middle" fill="{ac}" font-family="system-ui,-apple-system,sans-serif" font-size="11">{v:.2f}</text>')
    # Axis labels
    lines.append(f'<text x="{m["l"]+pw/2}" y="{_SVG_H-6}" text-anchor="middle" fill="{tc}" font-family="system-ui,-apple-system,sans-serif" font-size="13" font-weight="500">{escape(xlabel)}</text>')
    lines.append(f'<text x="18" y="{m["t"]+ph/2}" text-anchor="middle" fill="{tc}" font-family="system-ui,-apple-system,sans-serif" font-size="13" font-weight="500" transform="rotate(-90,18,{m["t"]+ph/2})">{escape(ylabel)}</text>')

    return "\n".join(lines), x_min, x_max, y_min, y_max


def _svg_linechart(traces: list[dict[str, Any]], xlabel: str = "Frequency (GHz)", ylabel: str = "S11 (dB)", dark: bool = False) -> str:
    all_x = [v for t in traces for v in t.get("x", [])]
    all_y = [v for t in traces for v in t.get("y", [])]
    if not all_x or not all_y:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"><text x="20" y="40">无数据</text></svg>'

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
    tc = _DARK_TEXT if dark else _LIGHT_TEXT
    tc = _DARK_TEXT if dark else _LIGHT_TEXT

    for idx, trace in enumerate(traces):
        xs = trace.get("x", [])
        ys = trace.get("y", [])
        if not xs or not ys:
            continue
        color = _COLORS[idx % len(_COLORS)]
        label = trace.get("name", f"Trace {idx+1}")

        # Area fill
        pts_fill = " ".join(f"{sx(x)},{sy(y)}" for x, y in zip(xs, ys) if not (math.isnan(y) or math.isinf(y)))
        first_x, last_x = sx(xs[0]), sx(xs[-1])
        baseline_y = sy(y_min + y_pad)
        parts.append(
            f'<polygon points="{pts_fill} {last_x},{baseline_y} {first_x},{baseline_y}" '
            f'fill="{color}" fill-opacity="0.08" stroke="none"/>'
        )

        # Line
        pts = " ".join(f"{sx(x)},{sy(y)}" for x, y in zip(xs, ys) if not (math.isnan(y) or math.isinf(y)))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>')

        # Min point marker
        valid_pairs = [(x, y) for x, y in zip(xs, ys) if not (math.isnan(y) or math.isinf(y))]
        if valid_pairs:
            min_pair = min(valid_pairs, key=lambda p: p[1])
            mx, my = sx(min_pair[0]), sy(min_pair[1])
            parts.append(f'<circle cx="{mx}" cy="{my}" r="4" fill="{color}" stroke="{tc}" stroke-width="1.5"><title>{label} min: {min_pair[1]:.2f} dB at {min_pair[0]:.3f} GHz</title></circle>')

        # Legend
        ly = m["t"] + 20 + idx * 24
        parts.append(f'<line x1="{m["l"]+pw-130}" y1="{ly}" x2="{m["l"]+pw-106}" y2="{ly}" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>')
        parts.append(f'<circle cx="{m["l"]+pw-118}" cy="{ly}" r="3" fill="{color}"/>')
        parts.append(f'<text x="{m["l"]+pw-100}" y="{ly+4}" fill="{tc}" font-family="system-ui,-apple-system,sans-serif" font-size="12" font-weight="500">{escape(label)}</text>')

    return f'<svg width="{_SVG_W}" height="{_SVG_H}" xmlns="http://www.w3.org/2000/svg">\n' + "\n".join(parts) + "\n</svg>"


def _svg_heatmap(x: list[float], y: list[float], z: list[list[float]], title: str, xlabel: str, ylabel: str, zlabel: str) -> str:
    if not x or not y or not z:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"><text x="20" y="40">无数据</text></svg>'
    nx, ny = len(x), len(y)
    m = _SVG_MARGIN
    pw = _SVG_W - m["l"] - m["r"] - 60
    ph = _SVG_H - m["t"] - m["b"]
    cw, ch = pw / nx, ph / ny

    all_z = [v for row in z for v in row if v is not None]
    if not all_z:
        return f'<svg width="{_SVG_W}" height="{_SVG_H}"><text x="20" y="40">无数据</text></svg>'
    z_min, z_max = min(all_z), max(all_z)
    z_rng = z_max - z_min or 1

    def _color(v):
        if v is None:
            return "#e4e4e7"
        t = (v - z_min) / z_rng
        # Warm teal gradient: deep teal -> light amber
        r = int(13 + (217 - 13) * t)
        g = int(148 + (119 - 148) * t)
        b = int(136 + (6 - 136) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    parts = [f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" fill="#ffffff" rx="6"/>']
    parts.append(f'<text x="{_SVG_W/2}" y="24" text-anchor="middle" font-size="14" font-weight="600" font-family="system-ui,-apple-system,sans-serif" fill="#18181b">{escape(title)}</text>')

    for i in range(ny):
        for j in range(nx):
            v = z[i][j] if i < len(z) and j < len(z[i]) else None
            xx = m["l"] + j * cw
            yy = m["t"] + i * ch
            parts.append(f'<rect x="{xx}" y="{yy}" width="{cw}" height="{ch}" fill="{_color(v)}" stroke="none"><title>{xlabel}: {x[j]:.2f}, {ylabel}: {y[i]:.2f}, {zlabel}: {v if v is not None else "N/A"}</title></rect>')

    # Colorbar
    cb_x = m["l"] + pw + 12
    cb_h = ph
    cb_w = 18
    cb_steps = 24
    for i in range(cb_steps):
        t = i / cb_steps
        v = z_min + t * z_rng
        yy = m["t"] + cb_h - (cb_h * t)
        ch_step = cb_h / cb_steps + 1
        parts.append(f'<rect x="{cb_x}" y="{yy}" width="{cb_w}" height="{ch_step}" fill="{_color(v)}" stroke="none"/>')
    # Colorbar border
    parts.append(f'<rect x="{cb_x}" y="{m["t"]}" width="{cb_w}" height="{cb_h}" fill="none" stroke="#d4d4d8" stroke-width="1" rx="2"/>')
    parts.append(f'<text x="{cb_x+cb_w+6}" y="{m["t"]+12}" fill="#18181b" font-family="system-ui,-apple-system,sans-serif" font-size="10" font-weight="500">{z_max:.2f}</text>')
    parts.append(f'<text x="{cb_x+cb_w+6}" y="{m["t"]+cb_h+4}" fill="#18181b" font-family="system-ui,-apple-system,sans-serif" font-size="10" font-weight="500">{z_min:.2f}</text>')
    parts.append(f'<text x="{cb_x+cb_w+6}" y="{m["t"]+cb_h/2+4}" fill="#18181b" font-family="system-ui,-apple-system,sans-serif" font-size="10" transform="rotate(-90,{cb_x+cb_w+6},{m["t"]+cb_h/2+4})">{escape(zlabel)}</text>')

    # Axis labels
    fill_c = "#18181b"
    x_step = max(1, nx // 8)
    for j in range(0, nx, x_step):
        parts.append(f'<text x="{m["l"]+j*cw+cw/2}" y="{m["t"]+ph+14}" text-anchor="middle" fill="{fill_c}" font-family="system-ui,-apple-system,sans-serif" font-size="10">{x[j]:.1f}</text>')
    y_step = max(1, ny // 6)
    for i in range(0, ny, y_step):
        parts.append(f'<text x="{m["l"]-8}" y="{m["t"]+i*ch+ch/2+3}" text-anchor="end" fill="{fill_c}" font-family="system-ui,-apple-system,sans-serif" font-size="10">{y[i]:.1f}</text>')
    parts.append(f'<text x="{m["l"]+pw/2}" y="{_SVG_H-4}" text-anchor="middle" fill="{fill_c}" font-family="system-ui,-apple-system,sans-serif" font-size="12" font-weight="500">{escape(xlabel)}</text>')
    parts.append(f'<text x="16" y="{m["t"]+ph/2}" text-anchor="middle" fill="{fill_c}" font-family="system-ui,-apple-system,sans-serif" font-size="12" font-weight="500" transform="rotate(-90,16,{m["t"]+ph/2})">{escape(ylabel)}</text>')

    return f'<svg width="{_SVG_W}" height="{_SVG_H}" xmlns="http://www.w3.org/2000/svg">\n' + "\n".join(parts) + "\n</svg>"


def _svg_page(
    title: str,
    body_svg: str,
    dark: bool = False,
    extra_html: str = "",
    metrics_html: str = "",
    subtitle: str = "",
) -> str:
    timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
:root{{
--bg:#f8f9fa;--bg-card:#fff;--bg-raised:#f1f5f9;--text:#18181b;--text-secondary:#52525b;--text-muted:#a1a1aa;--border:#e4e4e7;--accent:#0d9488;--accent-hover:#0f766e;--accent-subtle:rgba(13,148,136,.08);--success:#059669;--warning:#d97706;--danger:#dc2626;--shadow-sm:0 1px 2px rgba(0,0,0,.04);--shadow:0 1px 3px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.04);--shadow-md:0 4px 6px -1px rgba(0,0,0,.06),0 2px 4px -2px rgba(0,0,0,.04);--radius:16px;--radius-sm:8px;--transition:all .25s cubic-bezier(.16,1,.3,1)
}}
@media(prefers-color-scheme:dark){{
:root{{
--bg:#09090b;--bg-card:#18181b;--bg-raised:#27272a;--text:#f4f4f5;--text-secondary:#a1a1aa;--text-muted:#71717a;--border:#27272a;--accent:#2dd4bf;--accent-hover:#5eead4;--accent-subtle:rgba(45,212,191,.1);--shadow-sm:0 1px 2px rgba(0,0,0,.3);--shadow:0 1px 3px rgba(0,0,0,.4);--shadow-md:0 4px 6px -1px rgba(0,0,0,.5)
}}
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen,Ubuntu,Cantarell,"Helvetica Neue",sans-serif;background:var(--bg);color:var(--text);line-height:1.6;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}}
.container{{max-width:1280px;margin:0 auto;padding:40px 28px}}
.page-header{{margin-bottom:40px;text-align:left;max-width:720px}}
.page-header h1{{font-size:28px;font-weight:700;letter-spacing:-.02em;color:var(--text);line-height:1.2}}
.page-header .subtitle{{font-size:14px;color:var(--text-secondary);margin-top:6px;font-weight:400}}
.page-header .timestamp{{font-size:11px;color:var(--text-muted);margin-top:8px;text-transform:uppercase;letter-spacing:.04em}}
.metrics-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:36px}}
.metric-card{{background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;transition:var(--transition);position:relative;overflow:hidden;cursor:default}}
.metric-card:hover{{transform:translateY(-2px);box-shadow:var(--shadow-md);border-color:var(--accent)}}
.metric-card::after{{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent);opacity:0;transition:var(--transition)}}
.metric-card:hover::after{{opacity:1}}
.metric-label{{font-size:11px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.metric-value{{font-size:30px;font-weight:700;color:var(--text);line-height:1.1;letter-spacing:-.02em}}
.metric-value.accent{{color:var(--accent)}}
.metric-value.success{{color:var(--success)}}
.metric-unit{{font-size:13px;font-weight:400;color:var(--text-secondary);margin-left:3px}}
.charts-section{{margin-bottom:36px}}
.chart-panel{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:24px;margin-bottom:24px;box-shadow:var(--shadow-sm);transition:var(--transition)}}
.chart-panel:hover{{box-shadow:var(--shadow)}}
.chart-panel svg{{max-width:100%;height:auto;display:block;margin:0 auto;border-radius:4px}}
.chart-grid{{display:grid;grid-template-columns:1fr;gap:20px;margin-bottom:24px}}
@media(min-width:1060px){{.chart-grid.cols-2{{grid-template-columns:1fr 1fr}}}}
.data-section{{margin-bottom:36px}}
.section-title{{font-size:13px;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
table{{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}}
thead th{{font-weight:600;color:var(--text-secondary);text-transform:uppercase;font-size:11px;letter-spacing:.05em;padding:14px 16px;text-align:left;background:var(--bg-raised);border-bottom:2px solid var(--border)}}
tbody td{{padding:11px 16px;border-bottom:1px solid var(--border);color:var(--text);transition:var(--transition)}}
tbody tr{{transition:var(--transition)}}
tbody tr:hover td{{background:var(--accent-subtle)}}
tbody tr:last-child td{{border-bottom:none}}
tr.best td{{background:var(--accent-subtle);font-weight:600}}
@media(prefers-color-scheme:dark){{tr.best td{{background:rgba(45,212,191,.12)}}}}
.badge{{display:inline-flex;align-items:center;padding:2px 10px;border-radius:99px;font-size:10px;font-weight:600;letter-spacing:.02em;text-transform:uppercase}}
.badge-best{{background:rgba(5,150,105,.12);color:var(--success)}}
@media(prefers-color-scheme:dark){{.badge-best{{background:rgba(5,150,105,.22)}}}}
.badge-warn{{background:rgba(217,119,6,.12);color:var(--warning)}}
/* Step cards */
.step-list{{display:flex;flex-direction:column;gap:12px;margin-bottom:36px}}
.step-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden;transition:var(--transition)}}
.step-card:hover{{box-shadow:var(--shadow)}}
.step-header{{display:flex;align-items:center;gap:10px;padding:12px 16px;background:var(--bg-raised);border-bottom:1px solid var(--border);flex-wrap:wrap}}
.step-idx{{font-size:11px;font-weight:700;color:var(--accent);font-family:"SF Mono","Fira Code","Cascadia Code",monospace}}
.step-tool{{font-size:11px;font-weight:600;padding:2px 8px;border-radius:4px;text-transform:lowercase;letter-spacing:.02em}}
.step-tool.param_change,.step-tool.param_define{{background:rgba(13,148,136,.1);color:var(--accent)}}
.step-tool.simulation{{background:rgba(124,58,237,.1);color:#7c3aed}}
.step-tool.result{{background:rgba(5,150,105,.1);color:var(--success)}}
.step-tool.geometry,.step-tool.boolean,.step-tool.entity{{background:rgba(217,119,6,.1);color:var(--warning)}}
.step-ts{{font-size:10px;color:var(--text-muted);margin-left:auto;font-family:"SF Mono","Fira Code","Cascadia Code",monospace}}
.step-body{{padding:12px 16px}}
.step-summary{{font-size:13px;color:var(--text);margin-bottom:4px}}
.step-rationale{{font-size:12px;color:var(--text-secondary);font-style:italic}}
.s11-snippet{{margin-top:8px;padding:8px 12px;background:var(--bg-raised);border-radius:6px;display:inline-flex;gap:10px}}
.s11-min{{font-size:16px;font-weight:700;color:var(--success)}}
.s11-freq{{font-size:13px;color:var(--text-secondary)}}
.step-detail{{border-top:1px solid var(--border)}}
.step-detail summary{{padding:8px 16px;font-size:11px;color:var(--text-muted);cursor:pointer;user-select:none;transition:var(--transition)}}
.step-detail summary:hover{{color:var(--text)}}
.step-detail pre{{margin:0;padding:12px 16px;font-size:11px;font-family:"SF Mono","Fira Code","Cascadia Code",monospace;background:var(--bg);color:var(--text-secondary);overflow-x:auto;white-space:pre-wrap;max-height:300px;overflow-y:auto}}
/* Canvas 3D */
.chart-panel canvas{{max-width:100%;height:auto;display:block;margin:0 auto;border-radius:4px}}
footer{{margin-top:48px;padding-top:20px;border-top:1px solid var(--border);text-align:left}}
footer p{{color:var(--text-muted);font-size:11px;letter-spacing:.03em}}
</style>
</head>
<body>
<div class="container">
<header class="page-header">
<h1>{escape(title)}</h1>
{f'<div class="subtitle">{escape(subtitle)}</div>' if subtitle else ''}
<div class="timestamp">{timestamp_str}</div>
</header>
{metrics_html}
<div class="charts-section">
{body_svg}
</div>
{extra_html}
<footer><p>CST Runtime CLI — 电磁仿真优化报告</p></footer>
</div>
</body>
</html>"""


def _metric_cards_html(metrics: list[dict[str, str]]) -> str:
    if not metrics:
        return ""
    cards = []
    for m in metrics:
        css_class = m.get("css_class", "")
        cards.append(
            f'<div class="metric-card">'
            f'<div class="metric-label">{escape(m["label"])}</div>'
            f'<div class="metric-value {css_class}">{escape(m["value"])}'
            f'{f'<span class="metric-unit">{escape(m["unit"])}</span>' if m.get("unit") else ""}'
            f'</div>'
            f'</div>'
        )
    return f'<div class="metrics-grid">{"".join(cards)}</div>'


# ── Optimization timeline builder ──

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
            import ast
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
    for fpath in sorted(d.glob("s11_run*.json")):
        try:
            payload = json.loads(fpath.read_text(encoding="utf-8-sig"))
            if "xdata" not in payload or "ydata" not in payload:
                continue
            run_id = payload.get("run_id", 0)
            db_values: list[float] = []
            for item in payload.get("ydata", []):
                real = item.get("real", 0) if isinstance(item, dict) else float(item) if isinstance(item, (int, float)) else 0
                imag = item.get("imag", 0) if isinstance(item, dict) else 0
                db_values.append(_safe_log_db(math.hypot(real, imag)))
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


# ── Mini SVG trend chart ──

def _svg_mini_trend(points: list[float], width: int = 320, height: int = 100, label: str = "") -> str:
    if not points:
        return ""
    n = len(points)
    pad = 8
    pw = width - pad * 2
    ph = height - pad * 2
    y_min = min(points)
    y_max = max(points)
    y_rng = y_max - y_min or 1
    y_min -= y_rng * 0.1
    y_max += y_rng * 0.1

    def sx(i): return pad + i / max(n - 1, 1) * pw
    def sy(v): return pad + ph - (v - y_min) / (y_max - y_min) * ph

    pts = " ".join(f"{sx(i)},{sy(v)}" for i, v in enumerate(points) if not (math.isnan(v) or math.isinf(v)))
    fill_pts = f"{pts} {sx(n-1)},{height - pad} {sx(0)},{height - pad}"

    svg = f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
    svg += f'<rect x="0" y="0" width="{width}" height="{height}" fill="none"/>'
    svg += f'<polygon points="{fill_pts}" fill="#0d9488" fill-opacity="0.08"/>'
    svg += f'<polyline points="{pts}" fill="none" stroke="#0d9488" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    if n > 0 and points:
        last_val = points[-1]
        svg += f'<circle cx="{sx(n-1)}" cy="{sy(last_val)}" r="3" fill="#0d9488"/>'
    if label:
        svg += f'<text x="{width-pad}" y="{pad+8}" text-anchor="end" fill="#a1a1aa" font-family="system-ui,sans-serif" font-size="9">{escape(label)}</text>'
    svg += "</svg>"
    return svg


# ── Step card HTML ──

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

    # Build collapse detail JSON
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
                        db_vals.append(_safe_log_db(math.hypot(real, imag)))
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
    <span class="step-tool {category}">{tool}</span>
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


# ── 3D Farfield Canvas renderer ──

def _render_3d_farfield(data: dict[str, Any], container_id: str = "ff3d") -> str:
    theta = data.get("ypositions", [])
    phi = data.get("xpositions", [])
    gain = data.get("data", [])
    if not theta or not phi or not gain:
        return '<div class="chart-panel"><p>无可用的远场数据，无法渲染 3D 视图</p></div>'

    # Build triangle mesh from grid
    ny = len(theta)
    nx = len(phi)
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    values: list[float | None] = []
    raw_vals: list[float | None] = []
    for i in range(ny):
        for j in range(nx):
            g = gain[i][j] if i < len(gain) and j < len(gain[i]) else None
            raw_vals.append(float(g) if g is not None else None)
    valid_vals = [v for v in raw_vals if v is not None]
    val_min = min(valid_vals) if valid_vals else -40
    val_max = max(valid_vals) if valid_vals else 14
    val_rng = max(val_max - val_min, 1)
    max_radius = 0.0
    for i in range(ny):
        for j in range(nx):
            g = raw_vals[i * nx + j]
            if g is None:
                r = 0.1
                v = None
            else:
                r = (g - val_min) / val_rng * 4.5 + 0.3
                v = g
                max_radius = max(max_radius, r)
            th = math.radians(float(theta[i]))
            ph = math.radians(float(phi[j]))
            x = r * math.sin(th) * math.cos(ph)
            y = r * math.sin(th) * math.sin(ph)
            z = r * math.cos(th)
            vertices.append([x, y, z])
            values.append(v)
    # Build faces from uniform grid quads (all rows treated equally)
    for i in range(ny - 1):
        for j in range(nx - 1):
            a = i * nx + j
            b = a + 1
            c = a + nx
            d = c + 1
            va, vb, vc, vd = values[a], values[b], values[c], values[d]
            if va is not None and vb is not None and vc is not None:
                faces.append([a, b, c, (va + vb + vc) / 3])
            if vb is not None and vd is not None and vc is not None:
                faces.append([b, d, c, (vb + vd + vc) / 3])

    if not faces:
        return '<div class="chart-panel"><p>无有效的远场网格数据</p></div>'

    # Build sorted face values for percentile-based color mapping
    z_all = sorted(f[3] for f in faces)
    z_count = len(z_all)

    camera_dist = max(max_radius * 2.5, 6)
    initial_zoom = 1.0

    vertices_json = json.dumps(vertices, separators=(",", ":"))
    faces_json = json.dumps(faces, separators=(",", ":"))
    z_sorted_json = json.dumps(z_all, separators=(",", ":"))

    js = f'''<canvas id="{container_id}" style="width:100%;min-height:460px;display:block;border-radius:12px;background:#18181b;"></canvas>
<script>
(function(){{
var V={vertices_json},F={faces_json};
var Z={z_sorted_json},zCnt={z_count};
var camDist={camera_dist:.1f},maxR={max_radius:.2f};
var cnv=document.getElementById("{container_id}");
if(!cnv)return;
var ctx=cnv.getContext("2d");
if(!ctx)return;
var W=Math.max(cnv.clientWidth||800,400),H=Math.max(W*0.75,350);
var zoom={initial_zoom:.1f},cx=0,cy=0;
var M=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
var M0=M.slice();
var dragging=false,lastSx=0,lastSy=0;
var autoRotate=0,autoRAF=0;

function startAuto(){{if(!autoRotate){{autoRotate=1;cnv.__autoRAF=requestAnimationFrame(autoFrame);}}}}
function stopAuto(){{autoRotate=0;if(cnv.__autoRAF){{cancelAnimationFrame(cnv.__autoRAF);cnv.__autoRAF=0;}}}}
function autoFrame(){{if(autoRotate){{M=matMul(axisAngle(0,0,1,0.008),M);draw();cnv.__autoRAF=requestAnimationFrame(autoFrame);}}}}
function resetView(){{stopAuto();M=M0.slice();zoom={initial_zoom:.1f};draw();}}

function resize(){{W=Math.max(cnv.clientWidth||800,400);H=Math.max(W*0.75,350);cnv.width=W;cnv.height=H;draw();}}

function colorMap(v){{var lo=0,hi=zCnt-1,mid;while(lo<=hi){{mid=(lo+hi)>>1;if(Z[mid]<v)lo=mid+1;else hi=mid-1;}}var t=Math.max(0,lo)/Math.max(zCnt-1,1);
var stops=[0,0.16,0.33,0.5,0.66,0.83,1];
var rs=[5,0,0,0,255,255,255],gs=[5,100,200,255,220,120,255],bs=[30,200,255,0,0,0,255];
var seg=0;while(seg<6&&t>stops[seg+1])seg++;
var s=(t-stops[seg])/(stops[seg+1]-stops[seg]+0.0001);
var r=Math.round(rs[seg]+s*(rs[seg+1]-rs[seg]));
var g=Math.round(gs[seg]+s*(gs[seg+1]-gs[seg]));
var b=Math.round(bs[seg]+s*(bs[seg+1]-bs[seg]));
return"rgb("+r+","+g+","+b+")";}}

function matMulVec(m,v){{var x=v[0],y=v[1],z=v[2];
return[x*m[0]+y*m[4]+z*m[8]+m[12],x*m[1]+y*m[5]+z*m[9]+m[13],x*m[2]+y*m[6]+z*m[10]+m[14]];}}

function matMul(a,b){{var r=new Array(16);
for(var i=0;i<4;i++)for(var j=0;j<4;j++){{var s=0;for(var k=0;k<4;k++)s+=a[i+k*4]*b[k+j*4];r[i+j*4]=s;}}
return r;}}

function axisAngle(ax,ay,az,angle){{
var c=Math.cos(angle),s=Math.sin(angle),t=1-c;
var x=ax,y=ay,z=az;
return[t*x*x+c, t*x*y+s*z, t*x*z-s*y, 0,
       t*x*y-s*z, t*y*y+c, t*y*z+s*x, 0,
       t*x*z+s*y, t*y*z-s*x, t*z*z+c, 0,
       0, 0, 0, 1];}}

function mapToSphere(x,y){{
var r=Math.min(W,H)*0.5;
var sx=(x-W/2)/r, sy=-(y-H/2)/r;
var len=Math.sqrt(sx*sx+sy*sy);
if(len>1){{sx/=len;sy/=len;len=1;}}
var sz=Math.sqrt(Math.max(0,1-len*len));
return[sx,sy,sz];}}

function project(v){{var p=matMulVec(M,v);
var x=p[0],y=p[1],z=p[2];
var s=zoom*maxR/camDist;
return{{x:W/2+(x+cx)*s*W/(2*maxR),y:H/2-(y+cy)*s*W/(2*maxR),z:z}};}}

function draw(){{
cnv.width=W;cnv.height=H;
ctx.clearRect(0,0,W,H);
ctx.fillStyle="#18181b";ctx.fillRect(0,0,W,H);
var proj=F.map(function(f){{return{{p:[project(V[f[0]]),project(V[f[1]]),project(V[f[2]])],v:f[3]}};}});
proj.sort(function(a,b){{var az=a.p[0].z+a.p[1].z+a.p[2].z,bz=b.p[0].z+b.p[1].z+b.p[2].z;return az-bz;}});
for(var i=0;i<proj.length;i++){{var p=proj[i];
ctx.fillStyle=colorMap(p.v);
ctx.strokeStyle="rgba(255,255,255,0.1)";
ctx.beginPath();ctx.moveTo(p.p[0].x,p.p[0].y);ctx.lineTo(p.p[1].x,p.p[1].y);ctx.lineTo(p.p[2].x,p.p[2].y);ctx.closePath();
ctx.fill();ctx.stroke();}}
}}

cnv.addEventListener("mousedown",function(e){{stopAuto();dragging=true;var r=cnv.getBoundingClientRect();lastSx=e.clientX-r.left;lastSy=e.clientY-r.top;cnv.style.cursor="grabbing";}});
window.addEventListener("mouseup",function(){{dragging=false;cnv.style.cursor="grab";}});
window.addEventListener("mousemove",function(e){{
if(!dragging)return;
var r=cnv.getBoundingClientRect();
var sx=e.clientX-r.left,sy=e.clientY-r.top;
var p0=mapToSphere(lastSx,lastSy);
var p1=mapToSphere(sx,sy);
var axis=[p0[1]*p1[2]-p0[2]*p1[1],p0[2]*p1[0]-p0[0]*p1[2],p0[0]*p1[1]-p0[1]*p1[0]];
var len=Math.sqrt(axis[0]*axis[0]+axis[1]*axis[1]+axis[2]*axis[2]);
if(len>1e-6){{axis[0]/=len;axis[1]/=len;axis[2]/=len;var dot=p0[0]*p1[0]+p0[1]*p1[1]+p0[2]*p1[2];dot=Math.max(-1,Math.min(1,dot));M=matMul(axisAngle(axis[0],axis[1],axis[2],Math.acos(dot)),M);}}
lastSx=sx;lastSy=sy;
draw();
}});
cnv.addEventListener("wheel",function(e){{e.preventDefault();zoom*=e.deltaY>0?0.9:1.1;zoom=Math.max(0.15,Math.min(8,zoom));draw();}});
cnv.addEventListener("touchstart",function(e){{stopAuto();if(e.touches.length==1){{dragging=true;var r=cnv.getBoundingClientRect();lastSx=e.touches[0].clientX-r.left;lastSy=e.touches[0].clientY-r.top;}}}});
cnv.addEventListener("touchmove",function(e){{if(!dragging||e.touches.length!=1)return;var r=cnv.getBoundingClientRect();var sx=e.touches[0].clientX-r.left,sy=e.touches[0].clientY-r.top;var p0=mapToSphere(lastSx,lastSy),p1=mapToSphere(sx,sy);var axis=[p0[1]*p1[2]-p0[2]*p1[1],p0[2]*p1[0]-p0[0]*p1[2],p0[0]*p1[1]-p0[1]*p1[0]];var len=Math.sqrt(axis[0]*axis[0]+axis[1]*axis[1]+axis[2]*axis[2]);if(len>1e-6){{axis[0]/=len;axis[1]/=len;axis[2]/=len;var dot=p0[0]*p1[0]+p0[1]*p1[1]+p0[2]*p1[2];dot=Math.max(-1,Math.min(1,dot));M=matMul(axisAngle(axis[0],axis[1],axis[2],Math.acos(dot)),M);}}lastSx=sx;lastSy=sy;draw();}});
cnv.addEventListener("touchend",function(){{dragging=false;}});
window.addEventListener("resize",resize);
// Initial gentle rotation
M=matMul(axisAngle(0,1,0,0.4),M);
M=matMul(axisAngle(1,0,0,-0.5),M);
M0=M.slice();
// Expose controls to buttons
cnv.resetView=resetView;
cnv.startAuto=startAuto;
cnv.stopAuto=stopAuto;
cnv.style.cursor="grab";
resize();
}})();
</script>'''
    return js


# ── Combined dashboard + audit page generators ──

def _optimization_s11_chart(s11_exports: dict[int, dict[str, Any]], dark: bool = False) -> str:
    if not s11_exports:
        return '<div class="chart-panel"><p>无 S11 导出数据</p></div>'
    traces = []
    for rid in sorted(s11_exports.keys()):
        e = s11_exports[rid]
        traces.append({"x": e["xdata"], "y": e["ydata"], "name": f"Run {rid}"})
    svg = _svg_linechart(traces, dark=dark)
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
    return _metric_cards_html(metrics) if metrics else ""


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

        target.write_text(_svg_page(title, f'<div class="chart-panel">{svg}</div>'), encoding="utf-8")
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
        grid_class = "chart-grid"
        if len(panel_svgs) >= 2:
            grid_class += " cols-2"
        combined_svg = f'<div class="{grid_class}">\n' + "\n".join(
            f'<div class="chart-panel">{s}</div>' for s in panel_svgs
        ) + "\n</div>"
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

        # Metric cards
        best_series = min(all_series, key=lambda s: s["min_db"])
        freq_min = min(s["xdata"][0] for s in all_series if s["xdata"])
        freq_max = max(s["xdata"][-1] for s in all_series if s["xdata"])
        freq_range = f"{freq_min:.3f} - {freq_max:.3f}"
        all_freqs = [f for s in all_series for f in s["xdata"]]

        metrics = [
            {"label": "最优 S11", "value": f"{best_series['min_db']:.2f}", "unit": "dB", "css_class": "success"},
            {"label": "最优频率", "value": f"{best_series['best_freq']:.3f}" if best_series['best_freq'] else "-", "unit": "GHz", "css_class": "accent"},
            {"label": "对比数量", "value": str(len(all_series)), "css_class": ""},
            {"label": "频率范围", "value": freq_range, "unit": "GHz", "css_class": ""},
        ]
        metrics_html = _metric_cards_html(metrics)

        # Table with best-row marking
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

        body_svg = f'<div class="chart-panel">{_svg_linechart(traces, dark=True)}</div>'
        html_path.write_text(
            _svg_page(title, body_svg, dark=True, extra_html=table_html, metrics_html=metrics_html,
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

        # Farfield panels
        farfield_panels: list[str] = []
        for item in farfield_items:
            farfield_panels.append(
                f'<div class="chart-panel">'
                f'{_svg_heatmap(item["x"], item["y"], item["z"], item["title"], item["xlabel"], item["ylabel"], item["zlabel"])}'
                f'</div>'
            )
        ff_grid_class = "chart-grid"
        if len(farfield_panels) >= 2:
            ff_grid_class += " cols-2"
        farfield_block = f'<div class="{ff_grid_class}">\n' + "\n".join(farfield_panels) + "\n</div>"

        # Metric cards
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
        metrics_html = _metric_cards_html(metrics)

        # Table
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

        body_svg = f'<div class="chart-panel">{s11_svg}</div>\n{farfield_block}'
        target.write_text(
            _svg_page(title, body_svg, extra_html=table_html, metrics_html=metrics_html,
                      subtitle=f"S11 运行：{len(s11_series)} | 远场面板：{len(farfield_items)}"),
            encoding="utf-8")
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


# ── Optimization Dashboard & Audit Trail ──

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

        # Farfield data
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

        # Metrics
        metrics_html = _optimization_metrics_html(s11_exports, timeline)

        # S11 chart
        s11_chart = _optimization_s11_chart(s11_exports)

        # 3D farfield block
        ff_3d = ""
        if ff_data:
            ff_3d = (
                f'<div class="chart-panel">'
                f'<h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em">3D 辐射方向图</h3>'
                f'<div style="margin-bottom:8px;display:flex;gap:8px;flex-wrap:wrap">'
                f'<button onclick="document.getElementById(\'ff3d_dash\').resetView()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">重置</button>'
                f'<button onclick="document.getElementById(\'ff3d_dash\').startAuto()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">自动旋转</button>'
                f'</div>'
                f'{_render_3d_farfield(ff_data, "ff3d_dash")}'
                f'</div>'
            )

        # Mini trend
        trend_html = ""
        if len(s11_exports) > 1:
            min_dbs = [s11_exports[rid]["min_db"] for rid in sorted(s11_exports.keys())]
            trend_svg = _svg_mini_trend(min_dbs, label="最优 S11 per iteration")
            trend_html = f'<div class="chart-panel"><h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em">收敛趋势</h3>{trend_svg}</div>'

        # Parameter changes summary
        param_table = _param_changes_table_html(timeline)

        # S11 table
        s11_table = _s11_table_html(s11_exports)

        # Timeline preview (last N steps)
        step_previews: list[str] = []
        significant = [r for r in timeline if _categorize_step(r) in {"param_change", "simulation", "result"}]
        for idx, r in enumerate(significant[-12:]):
            step_previews.append(_step_card_html(len(significant) - len(significant[-12:]) + idx + 1, r, s11_exports))
        timeline_preview_html = ""
        if step_previews:
            timeline_preview_html = (
                f'<div class="section-title">近期操作</div>'
                f'<div class="step-list">{"".join(step_previews)}</div>'
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
            _svg_page(title, body, extra_html="", metrics_html=metrics_html,
                      subtitle=f"优化运行：{rd.name} | S11 运行：{len(s11_exports)} | 参数变更：{sum(1 for r in timeline if _categorize_step(r) == 'param_change')}"),
            encoding="utf-8")

        return {
            "status": "success",
            "output_html": str(target),
            "s11_count": len(s11_exports),
            "timeline_count": len(timeline),
            "has_farfield_3d": bool(ff_data),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "generate_optimization_dashboard_failed",
            str(exc),
            run_dir=str(run_dir),
            runtime_module="cst_runtime.results",
        )


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

        # Farfield data
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

        # Metrics
        metrics_html = _optimization_metrics_html(s11_exports, timeline)

        # 3D farfield (full size)
        ff_full = ""
        if ff_data:
            ff_full = (
                f'<div class="chart-panel">'
                f'<h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.05em">3D 辐射方向图</h3>'
                f'<div style="margin-bottom:8px;display:flex;gap:8px;flex-wrap:wrap">'
                f'<button onclick="document.getElementById(\'ff3d_audit\').resetView()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">重置</button>'
                f'<button onclick="document.getElementById(\'ff3d_audit\').startAuto()" style="padding:4px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg-raised);color:var(--text);cursor:pointer;font-size:12px">自动旋转</button>'
                f'</div>'
                f'{_render_3d_farfield(ff_data, "ff3d_audit")}'
                f'</div>'
            )

        # S11 chart
        s11_chart = _optimization_s11_chart(s11_exports)

        # Full step-by-step audit
        step_cards: list[str] = []
        for idx, r in enumerate(timeline, 1):
            step_cards.append(_step_card_html(idx, r, s11_exports))
        step_list_html = ""
        if step_cards:
            step_list_html = (
                f'<div class="section-title">完整审计追踪 ({len(step_cards)} 条操作)</div>'
                f'<div class="step-list">{"".join(step_cards)}</div>'
            )

        # S11 table
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
            _svg_page(title, body, extra_html="", metrics_html=metrics_html,
                      subtitle=f"优化运行：{rd.name} | {len(timeline)} 操作 | {len(s11_exports)} 个 S11 导出"),
            encoding="utf-8")

        return {
            "status": "success",
            "output_html": str(target),
            "s11_count": len(s11_exports),
            "timeline_count": len(timeline),
            "has_farfield_3d": bool(ff_data),
            "runtime_module": "cst_runtime.results",
        }
    except Exception as exc:
        return error_response(
            "generate_optimization_audit_failed",
            str(exc),
            run_dir=str(run_dir),
            runtime_module="cst_runtime.results",
        )
