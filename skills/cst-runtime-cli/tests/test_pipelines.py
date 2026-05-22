from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

SCRIPTS = str(Path(__file__).resolve().parents[1] / "scripts")
sys.path.insert(0, SCRIPTS)

class TestPipelineHelpers:
    def test_safe_log_db_positive(self):
        from cst_runtime.cli.pipelines.impl import _safe_log_db
        assert abs(_safe_log_db(0.5) - 20 * math.log10(0.5)) < 0.01

    def test_safe_log_db_zero(self):
        from cst_runtime.cli.pipelines.impl import _safe_log_db
        assert abs(_safe_log_db(0) - 20 * math.log10(1e-15)) < 0.01

    def test_parse_s11_json_valid(self):
        from cst_runtime.cli.pipelines.impl import _parse_s11_json
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s11_run1.json"
            payload = {
                "run_id": 1,
                "xdata": [9.0, 10.0, 11.0],
                "ydata": [
                    {"real": 0.3, "imag": 0.0},
                    {"real": 0.1, "imag": 0.0},
                    {"real": 0.2, "imag": 0.0},
                ],
            }
            p.write_text(json.dumps(payload), encoding="utf-8")
            result = _parse_s11_json(str(p))
            assert result is not None
            assert result["run_id"] == 1
            assert result["min_db"] < -10  # -20 dB for 0.1
            assert abs(result["best_freq"] - 10.0) < 0.1

    def test_parse_s11_json_complex_yielddata(self):
        from cst_runtime.cli.pipelines.impl import _parse_s11_json
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s11_run2.json"
            payload = {
                "run_id": 2,
                "xdata": [9.0, 10.0],
                "ydata": [0.2, 0.05],
            }
            p.write_text(json.dumps(payload), encoding="utf-8")
            result = _parse_s11_json(str(p))
            assert result is not None
            assert abs(result["best_freq"] - 10.0) < 0.1

    def test_parse_s11_json_empty(self):
        from cst_runtime.cli.pipelines.impl import _parse_s11_json
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.json"
            p.write_text("{}", encoding="utf-8")
            result = _parse_s11_json(str(p))
            assert result is None

    def test_parse_s11_json_missing_file(self):
        from cst_runtime.cli.pipelines.impl import _parse_s11_json
        result = _parse_s11_json(str(Path("/nonexistent/file.json")))
        assert result is None
