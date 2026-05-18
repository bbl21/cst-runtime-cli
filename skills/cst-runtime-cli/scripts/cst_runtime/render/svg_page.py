from __future__ import annotations

import time
from html import escape


def svg_page(
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
.step-detail summary{{padding:8px 16px;font-size:11px;color:var(--text-muted);cursor:pointer;user-select:none;transition:var(--transition)}}
.step-detail summary:hover{{color:var(--text)}}
.step-detail pre{{margin:0;padding:12px 16px;font-size:11px;font-family:"SF Mono","Fira Code","Cascadia Code",monospace;background:var(--bg);color:var(--text-secondary);overflow-x:auto;white-space:pre-wrap;max-height:300px;overflow-y:auto}}
/* Canvas 3D */
.chart-panel canvas{{max-width:100%;height:auto;display:block;margin:0 auto;border-radius:4px}}
.section-h2{{font-size:16px;font-weight:600;color:var(--text);margin:36px 0 16px;padding-bottom:8px;border-bottom:1px solid var(--border)}}
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
<footer><p>CST Runtime CLI \u2014 \u7535\u78c1\u4eff\u771f\u4f18\u5316\u62a5\u544a</p></footer>
</div>
</body>
</html>"""


def metric_cards_html(metrics: list[dict[str, str]]) -> str:
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