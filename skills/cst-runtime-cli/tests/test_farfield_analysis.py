"""Unit tests for cst_runtime.farfield_analysis (no CST required)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cst_runtime.farfield_analysis.parser import (
    _extract_farfield_frequency_ghz,
    _parse_farfield_cut_payload,
    inspect_farfield_ascii_grid,
)
from cst_runtime.farfield_analysis.flatness import (
    _build_farfield_angle_values,
    calculate_farfield_neighborhood_flatness,
)


class ParserExtractFrequencyTest(unittest.TestCase):
    """_extract_farfield_frequency_ghz"""

    def test_standard_format(self) -> None:
        self.assertEqual(
            _extract_farfield_frequency_ghz("farfield (f=28.5) [1]"), 28.5
        )

    def test_integer_frequency(self) -> None:
        self.assertEqual(
            _extract_farfield_frequency_ghz("farfield (f=10) [1]"), 10.0
        )

    def test_no_frequency(self) -> None:
        self.assertIsNone(_extract_farfield_frequency_ghz("no frequency here"))

    def test_empty_string(self) -> None:
        self.assertIsNone(_extract_farfield_frequency_ghz(""))

    def test_no_match_pattern(self) -> None:
        self.assertIsNone(
            _extract_farfield_frequency_ghz("farfield (x=28.5) [1]")
        )


class ParserInspectAsciiGridTest(unittest.TestCase):
    """inspect_farfield_ascii_grid"""

    def _make_txt(self, tmpdir: str, lines: list[str]) -> str:
        p = Path(tmpdir) / "ff.txt"
        p.write_text("\n".join(lines), encoding="utf-8")
        return str(p)

    def test_three_data_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_txt(tmpdir, [
                "Theta Phi Abs(Realized Gain)[dBi]",
                "0 0 14.5",
                "10 180 13.6",
                "20 90 12.0",
            ])
            result = inspect_farfield_ascii_grid(path)
            self.assertEqual(result["row_count"], 3)
            self.assertEqual(result["theta_count"], 3)
            self.assertEqual(result["phi_count"], 3)
            self.assertEqual(result["theta_min"], 0.0)
            self.assertEqual(result["theta_max"], 20.0)
            self.assertEqual(result["phi_min"], 0.0)
            self.assertEqual(result["phi_max"], 180.0)

    def test_header_only_skip_non_numeric(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_txt(tmpdir, ["Theta Phi Gain", "abc def 1.0"])
            result = inspect_farfield_ascii_grid(path)
            self.assertEqual(result["row_count"], 0)
            self.assertIsNone(result["theta_min"])

    def test_duplicate_theta_phi_are_deduped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_txt(tmpdir, [
                "0 0 10.0",
                "0 0 10.0",
                "0 90 11.0",
            ])
            result = inspect_farfield_ascii_grid(path)
            self.assertEqual(result["row_count"], 3)
            self.assertEqual(result["theta_count"], 1)
            self.assertEqual(result["phi_count"], 2)


class ParserParseCutPayloadTest(unittest.TestCase):
    """_parse_farfield_cut_payload"""

    def _make_json(
        self, tmpdir: str, data: dict, name: str = "cut.json"
    ) -> str:
        p = Path(tmpdir) / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return str(p)

    def test_basic_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_json(tmpdir, {
                "angle_deg": [0, 1, 2],
                "primary_db": [10, 11, 12],
            })
            result = _parse_farfield_cut_payload(path)
            self.assertEqual(len(result["samples"]), 3)
            self.assertEqual(result["samples"][0], (0.0, 10.0))
            self.assertEqual(result["samples"][1], (1.0, 11.0))
            self.assertEqual(result["samples"][2], (2.0, 12.0))
            self.assertEqual(result["label"], "cut")
            self.assertIn("file_path", result)

    def test_with_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_json(tmpdir, {
                "angle_deg": [0.0, 5.0],
                "primary_db": [14.0, 13.5],
                "frequency_ghz": 28.5,
                "port": 1,
                "cut": "phi",
                "const_axis_value": 0.0,
            })
            result = _parse_farfield_cut_payload(path)
            self.assertEqual(len(result["samples"]), 2)
            self.assertEqual(result["frequency_ghz"], 28.5)
            self.assertEqual(result["port"], 1)
            self.assertEqual(result["cut"], "phi")
            self.assertEqual(result["const_axis_value"], 0.0)

    def test_empty_samples_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_json(tmpdir, {
                "angle_deg": [],
                "primary_db": [],
            })
            with self.assertRaises(ValueError):
                _parse_farfield_cut_payload(path)

    def test_mismatched_lengths_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_json(tmpdir, {
                "angle_deg": [0, 1],
                "primary_db": [10],
            })
            with self.assertRaises(ValueError):
                _parse_farfield_cut_payload(path)

    def test_missing_keys_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._make_json(tmpdir, {"xdata": [1]})
            with self.assertRaises(ValueError):
                _parse_farfield_cut_payload(path)


class FlatnessBuildAngleValuesTest(unittest.TestCase):
    """_build_farfield_angle_values"""

    def test_basic_range(self) -> None:
        result = _build_farfield_angle_values(0, 10, 5, upper_bound=180)
        self.assertEqual(result, [0, 5, 10])

    def test_exclude_upper_endpoint(self) -> None:
        result = _build_farfield_angle_values(
            0, 360, 90, upper_bound=360, exclude_upper_endpoint=True
        )
        self.assertEqual(result, [0, 90, 180, 270])

    def test_single_point(self) -> None:
        result = _build_farfield_angle_values(0, 0, 1, upper_bound=180)
        self.assertEqual(result, [0])

    def test_negative_step_raises(self) -> None:
        with self.assertRaises(ValueError):
            _build_farfield_angle_values(0, 10, -1, upper_bound=180)

    def test_zero_step_raises(self) -> None:
        with self.assertRaises(ValueError):
            _build_farfield_angle_values(0, 10, 0, upper_bound=180)

    def test_exceeds_upper_bound_raises(self) -> None:
        with self.assertRaises(ValueError):
            _build_farfield_angle_values(0, 200, 10, upper_bound=180)

    def test_min_gt_max_raises(self) -> None:
        with self.assertRaises(ValueError):
            _build_farfield_angle_values(20, 10, 5, upper_bound=180)

    def test_negative_minimum_raises(self) -> None:
        with self.assertRaises(ValueError):
            _build_farfield_angle_values(-10, 10, 5, upper_bound=180)

    def test_step_larger_than_range(self) -> None:
        result = _build_farfield_angle_values(0, 3, 10, upper_bound=180)
        self.assertEqual(result, [0])


class FlatnessCalculateNeighborhoodTest(unittest.TestCase):
    """calculate_farfield_neighborhood_flatness"""

    def _make_cut_json(
        self, tmpdir: str, angles: list[float], gains: list[float], name: str
    ) -> str:
        p = Path(tmpdir) / name
        p.write_text(
            json.dumps({"angle_deg": angles, "primary_db": gains}),
            encoding="utf-8",
        )
        return str(p)

    def test_two_cuts_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            f0 = self._make_cut_json(
                tmpdir, [0, 5, 10, 15], [14.0, 13.9, 13.8, 13.7], "cut0.json"
            )
            f90 = self._make_cut_json(
                tmpdir, [0, 5, 10, 15], [13.5, 13.4, 13.3, 13.2], "cut90.json"
            )
            result = calculate_farfield_neighborhood_flatness(
                [f0, f90], theta_max_deg=15.0
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["file_count"], 2)
            self.assertEqual(len(result["per_file"]), 2)
            self.assertEqual(result["theta_max_deg"], 15.0)
            self.assertIn("grouped_summary", result)
            self.assertEqual(
                result["runtime_module"], "cst_runtime.farfield_analysis"
            )

    def test_theta_max_zero_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            f0 = self._make_cut_json(
                tmpdir, [0, 5], [14.0, 13.9], "cut0.json"
            )
            result = calculate_farfield_neighborhood_flatness(
                [f0], theta_max_deg=0
            )
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["error_type"], "farfield_flatness_failed")

    def test_empty_file_paths_returns_error(self) -> None:
        result = calculate_farfield_neighborhood_flatness([])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "farfield_flatness_failed")

    def test_no_samples_in_theta_range_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            f0 = self._make_cut_json(
                tmpdir, [20, 25], [14.0, 13.9], "cut0.json"
            )
            result = calculate_farfield_neighborhood_flatness(
                [f0], theta_max_deg=15.0
            )
            self.assertEqual(result["status"], "error")

    def test_output_json_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            f0 = self._make_cut_json(
                tmpdir, [0, 5, 10, 15], [14.0, 13.9, 13.8, 13.7], "cut0.json"
            )
            out = Path(tmpdir) / "flatness.json"
            result = calculate_farfield_neighborhood_flatness(
                [f0], theta_max_deg=15.0, output_json=str(out)
            )
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["output_json"], str(out))
            self.assertTrue(out.exists())
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(written["status"], "success")

    def test_grouped_summary_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            f0 = self._make_cut_json(
                tmpdir, [0, 5, 10, 15], [14.0, 13.9, 13.8, 13.7], "cut0.json"
            )
            f90 = self._make_cut_json(
                tmpdir, [0, 5, 10, 15], [13.5, 13.4, 13.3, 13.2], "cut90.json"
            )
            result = calculate_farfield_neighborhood_flatness(
                [f0, f90], theta_max_deg=15.0
            )
            grouped = result["grouped_summary"]
            self.assertIsInstance(grouped, list)
            self.assertGreater(len(grouped), 0)
            entry = grouped[0]
            self.assertIn("frequency_ghz", entry)
            self.assertIn("port", entry)
            self.assertIn("cut_count", entry)
            self.assertIn("cuts", entry)
            self.assertIn("worst_flatness_db", entry)
            self.assertIn("best_flatness_db", entry)
            self.assertIn("mean_flatness_db", entry)


if __name__ == "__main__":
    unittest.main()