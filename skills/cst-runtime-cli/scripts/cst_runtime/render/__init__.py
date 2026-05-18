from __future__ import annotations

from .svg_linechart import (
    _SVG_W, _SVG_H, _SVG_MARGIN, _COLORS,
    _DARK_BG, _DARK_TEXT, _LIGHT_BG, _LIGHT_TEXT,
    _svg_axes, svg_linechart, svg_mini_trend,
    complex_components, safe_log_db, scalar_series,
)
from .svg_heatmap import svg_heatmap
from .svg_page import svg_page, metric_cards_html
from .canvas_3d import render_3d_farfield
from .dashboard import (
    _TIMELINE_TOOLS, _SECTION_LABELS,
    _parse_cli_filename, _build_timeline,
    _categorize_step, _step_summary, _rationale_from_step,
    _load_s11_exports, load_s11_series, load_dashboard_farfield_items,
    _optimization_s11_chart, _s11_table_html,
    _optimization_metrics_html, _param_changes_table_html,
    _step_card_html, _load_exported_payload, _try_parse_cst_farfield_ascii,
    _plot_output_path,
    plot_exported_file, plot_farfield_multi,
    generate_s11_comparison, generate_s11_farfield_dashboard,
    generate_optimization_dashboard, generate_optimization_audit,
    generate_report,
)
