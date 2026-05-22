"""Pure-logic tests for core/gateway.py — no CST COM required."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "cst-runtime-cli"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from cst_runtime.core.gateway import (
    CstTrapError,
    ProjectState,
    _normalize,
    _ensure_state,
    _get_state,
    _remove_state,
    validate_project_path,
    guard_cross_session,
    guard_before_simulation,
    mark_params_dirty,
    clear_dirty,
    mark_farfield_exported,
    guard_before_close_save,
    compute_db,
    guard_farfield_quantity,
    annotate_change_param_result,
    guard_result_filter,
    on_session_open,
    on_session_close,
    _registry,
)


class GatewayRegistryTests:
    def test_normalize_windows_path(self):
        result = _normalize("C:\\foo\\bar\\test.cst")
        assert result == "C:/foo/bar/test.cst"

    def test_ensure_state_creates_entry(self):
        st = _ensure_state("C:/test.cst")
        assert st.path == "C:/test.cst"
        assert st.session_type == "unknown"
        assert st.stage == "clean"
        assert "C:/test.cst" in _registry

    def test_ensure_state_idempotent(self):
        st1 = _ensure_state("C:/test.cst")
        st2 = _ensure_state("C:/test.cst")
        assert st1 is st2

    def test_remove_state(self):
        _ensure_state("C:/test.cst")
        _remove_state("C:/test.cst")
        assert _get_state("C:/test.cst") is None


class GatewayT10ProjectPathTests:
    def test_empty_path_raises(self):
        with pytest.raises(ValueError):
            validate_project_path("")

    def test_directory_path_raises(self):
        with pytest.raises(ValueError):
            validate_project_path("C:/some/dir")

    def test_wrong_suffix_raises(self):
        with pytest.raises(ValueError):
            validate_project_path("C:/test.txt")

    def test_cst_file_passes(self):
        result = validate_project_path("C:/path/working.cst")
        assert result == "C:/path/working.cst"


class GatewayT2ParamsDirtyTests:
    def test_mark_params_dirty_sets_stage(self):
        _ensure_state("C:/test.cst")
        mark_params_dirty("C:/test.cst")
        st = _get_state("C:/test.cst")
        assert st.stage == "params_dirty"

    def test_guard_refuses_dirty_simulation(self):
        _ensure_state("C:/test.cst")
        mark_params_dirty("C:/test.cst")
        err = guard_before_simulation("C:/test.cst")
        assert err is not None
        assert err["status"] == "error"
        assert err["error_type"] == "params_not_rebuilt"
        assert err["trap"] == "T2_params_not_rebuilt"

    def test_guard_allows_clean_simulation(self):
        _ensure_state("C:/test.cst")
        err = guard_before_simulation("C:/test.cst")
        assert err is None

    def test_guard_allows_unknown_project(self):
        err = guard_before_simulation("C:/unknown.cst")
        assert err is None

    def test_clear_dirty_resets_stage(self):
        _ensure_state("C:/test.cst")
        mark_params_dirty("C:/test.cst")
        clear_dirty("C:/test.cst")
        st = _get_state("C:/test.cst")
        assert st.stage == "clean"


class GatewayT3FarfieldSaveTests:
    def test_mark_farfield_exported(self):
        _ensure_state("C:/test.cst")
        mark_farfield_exported("C:/test.cst")
        st = _get_state("C:/test.cst")
        assert st.stage == "farfield_exported"

    def test_guard_forces_save_false_after_export(self):
        _ensure_state("C:/test.cst")
        mark_farfield_exported("C:/test.cst")
        effective, msg = guard_before_close_save("C:/test.cst", True)
        assert not effective
        assert "T3" in msg

    def test_guard_allows_save_false(self):
        _ensure_state("C:/test.cst")
        mark_farfield_exported("C:/test.cst")
        effective, msg = guard_before_close_save("C:/test.cst", False)
        assert not effective
        assert msg == ""

    def test_guard_allows_save_on_clean_project(self):
        _ensure_state("C:/test.cst")
        effective, msg = guard_before_close_save("C:/test.cst", True)
        assert effective
        assert msg == ""

class GatewayT4ComplexDBTests:
    def test_compute_db_basic(self):
        ydata = [{"real": 0.3, "imag": 0.0}, {"real": 0.1, "imag": 0.0}]
        db = compute_db(ydata)
        assert len(db) == 2
        assert abs(db[0] - 20 * math.log10(0.3)) < 1e-9
        assert abs(db[1] - 20 * math.log10(0.1)) < 1e-9

    def test_compute_db_with_imag(self):
        ydata = [{"real": 3.0, "imag": 4.0}]
        db = compute_db(ydata)
        assert abs(db[0] - 20 * math.log10(5.0)) < 1e-9

    def test_compute_db_zero_value(self):
        ydata = [{"real": 0.0, "imag": 0.0}]
        db = compute_db(ydata)
        assert abs(db[0] - 20 * math.log10(1e-30)) < 1e-9


class GatewayT5T12SessionIsolationTests:
    def test_guard_allows_matching_session(self):
        _ensure_state("C:/test.cst")
        on_session_open("C:/test.cst", "modeler")
        err = guard_cross_session("C:/test.cst", "modeler")
        assert err is None

    def test_guard_rejects_cross_session(self):
        _ensure_state("C:/test.cst")
        on_session_open("C:/test.cst", "modeler")
        err = guard_cross_session("C:/test.cst", "results")
        assert err is not None
        assert err["status"] == "error"
        assert err["error_type"] == "cross_session_forbidden"

    def test_guard_allows_unknown_session(self):
        err = guard_cross_session("C:/unknown.cst", "results")
        assert err is None


class GatewayT8FarfieldQuantityTests:
    def test_realized_gain_passes(self):
        assert guard_farfield_quantity("Realized Gain") is None

    def test_gain_passes(self):
        assert guard_farfield_quantity("Gain") is None

    def test_directivity_passes(self):
        assert guard_farfield_quantity("Directivity") is None

    def test_abs_e_rejected(self):
        err = guard_farfield_quantity("Abs(E)")
        assert err is not None
        assert err["trap"] == "T8_abs_e_not_gain"

    def test_efield_rejected(self):
        err = guard_farfield_quantity("Efield")
        assert err is not None
        assert err["trap"] == "T8_abs_e_not_gain"

    def test_empty_passes_as_realized_gain(self):
        assert guard_farfield_quantity("") is None

    def test_unknown_quantity_rejected(self):
        err = guard_farfield_quantity("SomethingElse")
        assert err is not None
        assert err["error_type"] == "unsupported_quantity"

class GatewayT13ChangeParamAnnotationTests:
    def test_success_gets_warning(self):
        result = annotate_change_param_result({"status": "success", "changed": {"g": 23.0}})
        assert "warning" in result
        assert result["trap_note"] == "T13_restore_double_not_model_rebuild"

    def test_error_unchanged(self):
        result = annotate_change_param_result({"status": "error", "message": "oops"})
        assert "warning" not in result


class GatewayT14FilterTypeTests:
    def test_0d1d_passes(self):
        assert guard_result_filter("0D/1D") is None

    def test_colormap_passes(self):
        assert guard_result_filter("colormap") is None

    def test_all_passes(self):
        assert guard_result_filter("all") is None

    def test_invalid_rejected(self):
        err = guard_result_filter("wrong_filter")
        assert err is not None
        assert err["trap"] == "T14_tree_items_filter"

    def test_empty_defaults(self):
        assert guard_result_filter("") is None
