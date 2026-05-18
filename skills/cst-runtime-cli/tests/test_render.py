"""Unit tests for cst_runtime.render.* (no CST needed)."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from cst_runtime.render.svg_linechart import (
    _svg_axes,
    complex_components,
    safe_log_db,
    scalar_series,
    svg_linechart,
    svg_mini_trend,
)
from cst_runtime.render.svg_heatmap import svg_heatmap
from cst_runtime.render.svg_page import metric_cards_html, svg_page
from cst_runtime.render.canvas_3d import render_3d_farfield
from cst_runtime.render.dashboard import (
    _parse_cli_filename,
    _try_parse_cst_farfield_ascii,
    generate_s11_comparison,
)


class TestSvgLinechart(unittest.TestCase):
    """Tests for render/svg_linechart.py"""

    def test_safe_log_db_positive(self) -> None:
        val = safe_log_db(0.5)
        expected = 20.0 * math.log10(0.5)
        self.assertAlmostEqual(val, expected, places=10)

    def test_safe_log_db_zero(self) -> None:
        val = safe_log_db(0.0)
        expected = 20.0 * math.log10(1e-15)
        self.assertAlmostEqual(val, expected, places=10)

    def test_safe_log_db_negative_input(self) -> None:
        val = safe_log_db(-0.5)
        expected = 20.0 * math.log10(0.5)
        self.assertAlmostEqual(val, expected, places=10)

    def test_complex_components_dict(self) -> None:
        r, i = complex_components({"real": 0.5, "imag": 0.3})
        self.assertEqual(r, 0.5)
        self.assertEqual(i, 0.3)

    def test_complex_components_scalar(self) -> None:
        r, i = complex_components(0.7)
        self.assertEqual(r, 0.7)
        self.assertEqual(i, 0.0)

    def test_complex_components_list(self) -> None:
        r, i = complex_components([0.4, 0.6])
        self.assertEqual(r, 0.4)
        self.assertEqual(i, 0.6)

    def test_complex_components_empty_dict(self) -> None:
        r, i = complex_components({})
        self.assertEqual(r, 0.0)
        self.assertEqual(i, 0.0)

    def test_scalar_series_complex(self) -> None:
        values = [{"real": 0.5, "imag": 0.3}]
        result, kind = scalar_series(values)
        expected = safe_log_db(math.hypot(0.5, 0.3))
        self.assertEqual(kind, "magnitude_db")
        self.assertAlmostEqual(result[0], expected, places=10)

    def test_scalar_series_empty(self) -> None:
        result, kind = scalar_series([])
        self.assertEqual(result, [])
        self.assertEqual(kind, "value")

    def test_scalar_series_plain_numbers(self) -> None:
        result, kind = scalar_series([1.0, 2.0, 3.0])
        self.assertEqual(kind, "value")
        self.assertEqual(result, [1.0, 2.0, 3.0])

    def test_svg_linechart_has_svg(self) -> None:
        svg = svg_linechart([{"x": [9, 10, 11], "y": [-10, -15, -12], "name": "test"}])
        self.assertIn("<svg", svg)
        self.assertIn('width="960"', svg)
        self.assertIn('xmlns="http://www.w3.org/2000/svg"', svg)

    def test_svg_linechart_empty_traces(self) -> None:
        svg = svg_linechart([])
        self.assertIn("无数据", svg)

    def test_svg_mini_trend_has_svg(self) -> None:
        svg = svg_mini_trend([1, 2, 3])
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_svg_mini_trend_empty(self) -> None:
        self.assertEqual(svg_mini_trend([]), "")

    def test_svg_mini_trend_single_point(self) -> None:
        svg = svg_mini_trend([42.0])
        self.assertIn("<svg", svg)

    def test_svg_mini_trend_with_label(self) -> None:
        svg = svg_mini_trend([1, 2, 3], label="S11")
        self.assertIn("S11", svg)

    def test_svg_axes_has_rect(self) -> None:
        result, x_min, x_max, y_min, y_max = _svg_axes(
            0, 10, -40, 0, "Freq (GHz)", "S11 (dB)", False
        )
        self.assertIn("<rect", result)
        self.assertIn("Freq (GHz)", result)
        self.assertIn("S11 (dB)", result)
        self.assertLess(x_min, 0)
        self.assertGreater(x_max, 10)

    def test_svg_axes_dark_mode(self) -> None:
        result, *_ = _svg_axes(0, 10, -40, 0, "X", "Y", True)
        self.assertIn("#18181b", result)

    def test_svg_axes_single_value_range(self) -> None:
        result, *_ = _svg_axes(5, 5, -10, -10, "X", "Y", False)
        self.assertIn("<rect", result)


class TestSvgHeatmap(unittest.TestCase):
    """Tests for render/svg_heatmap.py"""

    def test_empty_input(self) -> None:
        svg = svg_heatmap([], [], [], "Title", "X", "Y", "Z")
        self.assertIn("无数据", svg)

    def test_partial_none_grid(self) -> None:
        svg = svg_heatmap(
            x=[0, 90],
            y=[0],
            z=[[10, None]],
            title="Partial",
            xlabel="X",
            ylabel="Y",
            zlabel="Z",
        )
        self.assertIn("<svg", svg)

    def test_all_none_z(self) -> None:
        svg = svg_heatmap(
            x=[0, 90],
            y=[0],
            z=[[None, None]],
            title="AllNone",
            xlabel="X",
            ylabel="Y",
            zlabel="Z",
        )
        self.assertIn("无数据", svg)


class TestSvgPage(unittest.TestCase):
    """Tests for render/svg_page.py"""

    def test_svg_page_doctype(self) -> None:
        html = svg_page("My Title", "<svg></svg>")
        self.assertIn("<!doctype html>", html)
        self.assertIn("My Title", html)
        self.assertIn("<svg></svg>", html)

    def test_svg_page_with_subtitle(self) -> None:
        html = svg_page("T", "<svg></svg>", subtitle="My Subtitle")
        self.assertIn("My Subtitle", html)

    def test_svg_page_with_extra_html(self) -> None:
        html = svg_page("T", "<svg></svg>", extra_html="<table></table>")
        self.assertIn("<table></table>", html)

    def test_svg_page_dark_mode(self) -> None:
        html = svg_page("T", "<svg></svg>", dark=True)
        self.assertIn("<!doctype html>", html)

    def test_metric_cards_html(self) -> None:
        metrics = [
            {"label": "Test", "value": "1.23", "unit": "dB", "css_class": "success"}
        ]
        html = metric_cards_html(metrics)
        self.assertIn("1.23", html)
        self.assertIn("dB", html)
        self.assertIn("metrics-grid", html)

    def test_metric_cards_html_empty(self) -> None:
        self.assertEqual(metric_cards_html([]), "")

    def test_metric_cards_html_multiple(self) -> None:
        metrics = [
            {"label": "A", "value": "1", "css_class": ""},
            {"label": "B", "value": "2", "unit": "GHz", "css_class": "accent"},
        ]
        html = metric_cards_html(metrics)
        self.assertIn("A", html)
        self.assertIn("B", html)
        self.assertIn("GHz", html)

    def test_metric_cards_html_accent(self) -> None:
        metrics = [{"label": "C", "value": "3", "css_class": "accent"}]
        html = metric_cards_html(metrics)
        self.assertIn("accent", html)


class TestDashboard(unittest.TestCase):
    """Tests for render/dashboard.py"""

    def test_try_parse_cst_farfield_ascii(self) -> None:
        text = "Theta Phi Abs(Realized Gain)[dBi]\n0 0 14.5\n10 180 13.6"
        result = _try_parse_cst_farfield_ascii(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "2d")
        self.assertGreater(len(result["xpositions"]), 0)
        self.assertGreater(len(result["ypositions"]), 0)
        self.assertGreater(len(result["data"]), 0)

    def test_try_parse_cst_farfield_ascii_no_header(self) -> None:
        result = _try_parse_cst_farfield_ascii("abc\n123")
        self.assertIsNone(result)

    def test_try_parse_cst_farfield_ascii_empty(self) -> None:
        result = _try_parse_cst_farfield_ascii("")
        self.assertIsNone(result)

    def test_try_parse_cst_farfield_ascii_invalid_header(self) -> None:
        result = _try_parse_cst_farfield_ascii("Theta\n0 0 14.5")
        self.assertIsNone(result)

    def test_try_parse_cst_farfield_ascii_with_phi_closure(self) -> None:
        text = "Theta Phi Abs(Gain)[dBi]\n0 0 10\n0 180 11\n0 359 12"
        result = _try_parse_cst_farfield_ascii(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "2d")

    def test_try_parse_cst_farfield_ascii_missing_columns(self) -> None:
        text = "Theta Phi Abs(Realized Gain)[dBi]\n0 0 14.5\nbad_line"
        result = _try_parse_cst_farfield_ascii(text)
        self.assertIsNotNone(result)

    def test_parse_cli_filename(self) -> None:
        info = _parse_cli_filename("cli_20260101_120000_123456_change-parameter.json")
        self.assertIsNotNone(info["tool"] == "change-parameter")
        self.assertEqual(info["tool"], "change-parameter")
        self.assertEqual(info["sort_key"], "20260101120000123456")

    def test_parse_cli_filename_non_cli(self) -> None:
        result = _parse_cli_filename("not_a_cli_file.txt")
        self.assertIsNone(result)

    def test_parse_cli_filename_with_dots(self) -> None:
        info = _parse_cli_filename("cli_20260101_120000_123456_define-brick.json")
        self.assertIsNotNone(info)
        self.assertEqual(info["tool"], "define-brick")

    def test_generate_s11_comparison_with_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            s11 = d / "s11.json"
            s11.write_text(
                json.dumps({
                    "run_id": 1,
                    "xdata": [9.0, 10.0, 11.0],
                    "ydata": [
                        {"real": 0.3, "imag": 0.0},
                        {"real": 0.1, "imag": 0.0},
                        {"real": 0.2, "imag": 0.0},
                    ],
                }),
                encoding="utf-8",
            )
            result = generate_s11_comparison(
                [str(s11)],
                output_html=str(d / "out.html"),
                page_title="S11 Test",
            )
            self.assertEqual(result["status"], "success")
            expected = d / "out.html"
            self.assertTrue(expected.exists())
            content = expected.read_text(encoding="utf-8")
            self.assertIn("S11 Test", content)
            self.assertIn("<!doctype html>", content)

    def test_generate_s11_comparison_empty_paths(self) -> None:
        result = generate_s11_comparison([])
        self.assertEqual(result["status"], "error")
        self.assertIn("error_type", result)


class TestCanvas3D(unittest.TestCase):
    """Tests for render/canvas_3d.py"""

    def test_empty_data(self) -> None:
        html = render_3d_farfield({})
        self.assertIn("无可用", html)

    def test_missing_positions(self) -> None:
        html = render_3d_farfield({"data": [[1]]})
        self.assertIn("无可用", html)

    def test_minimal_valid_data(self) -> None:
        data = {
            "ypositions": [0, 90],
            "xpositions": [0, 180],
            "data": [[10, 5], [8, 3]],
        }
        html = render_3d_farfield(data)
        self.assertIn("<canvas", html)

    def test_partial_none_data(self) -> None:
        data = {
            "ypositions": [0, 45, 90],
            "xpositions": [0, 90, 180],
            "data": [[10, 8, 6], [7, None, 5], [6, 4, 3]],
        }
        html = render_3d_farfield(data)
        self.assertIn("<canvas", html)


if __name__ == "__main__":
    unittest.main()