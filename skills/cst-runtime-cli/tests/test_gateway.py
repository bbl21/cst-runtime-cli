"""Pure-logic tests for core/gateway.py — no CST COM required."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

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
    resolve_run_id,
    compute_db,
    guard_execute_vba_entrypoint,
    guard_farfield_quantity,
    guard_farfield_run_id,
    annotate_change_param_result,
    guard_result_filter,
    on_session_open,
    on_session_close,
    _registry,
)


class GatewayRegistryTests(unittest.TestCase):
    def setUp(self):
        _registry.clear()

    def test_normalize_windows_path(self):
        result = _normalize("C:\\foo\\bar\\test.cst")
        self.assertEqual(result, "C:/foo/bar/test.cst")

    def test_ensure_state_creates_entry(self):
        st = _ensure_state("C:/test.cst")
        self.assertEqual(st.path, "C:/test.cst")
        self.assertEqual(st.session_type, "unknown")
        self.assertEqual(st.stage, "clean")
        self.assertIn("C:/test.cst", _registry)

    def test_ensure_state_idempotent(self):
        st1 = _ensure_state("C:/test.cst")
        st2 = _ensure_state("C:/test.cst")
        self.assertIs(st1, st2)

    def test_remove_state(self):
        _ensure_state("C:/test.cst")
        _remove_state("C:/test.cst")
        self.assertIsNone(_get_state("C:/test.cst"))


class GatewayT10ProjectPathTests(unittest.TestCase):
    def setUp(self):
        _registry.clear()

    def test_empty_path_raises(self):
        with self.assertRaises(ValueError):
            validate_project_path("")

    def test_directory_path_raises(self):
        with self.assertRaises(ValueError):
            validate_project_path("C:/some/dir")

    def test_wrong_suffix_raises(self):
        with self.assertRaises(ValueError):
            validate_project_path("C:/test.txt")

    def test_cst_file_passes(self):
        result = validate_project_path("C:/path/working.cst")
        self.assertEqual(result, "C:/path/working.cst")


class GatewayT2ParamsDirtyTests(unittest.TestCase):
    def setUp(self):
        _registry.clear()

    def test_mark_params_dirty_sets_stage(self):
        _ensure_state("C:/test.cst")
        mark_params_dirty("C:/test.cst")
        st = _get_state("C:/test.cst")
        self.assertEqual(st.stage, "params_dirty")

    def test_guard_refuses_dirty_simulation(self):
        _ensure_state("C:/test.cst")
        mark_params_dirty("C:/test.cst")
        err = guard_before_simulation("C:/test.cst")
        self.assertIsNotNone(err)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error_type"], "params_not_rebuilt")
        self.assertEqual(err["trap"], "T2_params_not_rebuilt")

    def test_guard_allows_clean_simulation(self):
        _ensure_state("C:/test.cst")
        err = guard_before_simulation("C:/test.cst")
        self.assertIsNone(err)

    def test_guard_allows_unknown_project(self):
        err = guard_before_simulation("C:/unknown.cst")
        self.assertIsNone(err)

    def test_clear_dirty_resets_stage(self):
        _ensure_state("C:/test.cst")
        mark_params_dirty("C:/test.cst")
        clear_dirty("C:/test.cst")
        st = _get_state("C:/test.cst")
        self.assertEqual(st.stage, "clean")


class GatewayT3FarfieldSaveTests(unittest.TestCase):
    def setUp(self):
        _registry.clear()

    def test_mark_farfield_exported(self):
        _ensure_state("C:/test.cst")
        mark_farfield_exported("C:/test.cst")
        st = _get_state("C:/test.cst")
        self.assertEqual(st.stage, "farfield_exported")

    def test_guard_forces_save_false_after_export(self):
        _ensure_state("C:/test.cst")
        mark_farfield_exported("C:/test.cst")
        effective, msg = guard_before_close_save("C:/test.cst", True)
        self.assertFalse(effective)
        self.assertIn("T3", msg)

    def test_guard_allows_save_false(self):
        _ensure_state("C:/test.cst")
        mark_farfield_exported("C:/test.cst")
        effective, msg = guard_before_close_save("C:/test.cst", False)
        self.assertFalse(effective)
        self.assertEqual(msg, "")

    def test_guard_allows_save_on_clean_project(self):
        _ensure_state("C:/test.cst")
        effective, msg = guard_before_close_save("C:/test.cst", True)
        self.assertTrue(effective)
        self.assertEqual(msg, "")


class GatewayT1RunIdTests(unittest.TestCase):
    def test_run_id_nonzero_passthrough(self):
        rid, msg = resolve_run_id(5, [1, 2, 3, 5])
        self.assertEqual(rid, 5)
        self.assertEqual(msg, "")

    def test_run_id_zero_resolves_to_latest(self):
        rid, msg = resolve_run_id(0, [1, 2, 3, 5])
        self.assertEqual(rid, 5)
        self.assertIn("T1", msg)

    def test_run_id_zero_single_run(self):
        rid, msg = resolve_run_id(0, [1])
        self.assertEqual(rid, 1)
        self.assertIn("T1", msg)

    def test_run_id_zero_no_positive(self):
        rid, msg = resolve_run_id(0, [0])
        self.assertEqual(rid, 0)
        self.assertIn("T1", msg)

    def test_run_id_zero_empty(self):
        rid, msg = resolve_run_id(0, [])
        self.assertEqual(rid, 0)
        self.assertIn("T1", msg)


class GatewayT4ComplexDBTests(unittest.TestCase):
    def test_compute_db_basic(self):
        ydata = [{"real": 0.3, "imag": 0.0}, {"real": 0.1, "imag": 0.0}]
        db = compute_db(ydata)
        self.assertEqual(len(db), 2)
        self.assertAlmostEqual(db[0], 20 * math.log10(0.3))
        self.assertAlmostEqual(db[1], 20 * math.log10(0.1))

    def test_compute_db_with_imag(self):
        ydata = [{"real": 3.0, "imag": 4.0}]
        db = compute_db(ydata)
        self.assertAlmostEqual(db[0], 20 * math.log10(5.0))

    def test_compute_db_zero_value(self):
        ydata = [{"real": 0.0, "imag": 0.0}]
        db = compute_db(ydata)
        self.assertAlmostEqual(db[0], 20 * math.log10(1e-30))


class GatewayT5T12SessionIsolationTests(unittest.TestCase):
    def setUp(self):
        _registry.clear()

    def test_guard_allows_matching_session(self):
        _ensure_state("C:/test.cst")
        on_session_open("C:/test.cst", "modeler")
        err = guard_cross_session("C:/test.cst", "modeler")
        self.assertIsNone(err)

    def test_guard_rejects_cross_session(self):
        _ensure_state("C:/test.cst")
        on_session_open("C:/test.cst", "modeler")
        err = guard_cross_session("C:/test.cst", "results")
        self.assertIsNotNone(err)
        self.assertEqual(err["status"], "error")
        self.assertEqual(err["error_type"], "cross_session_forbidden")

    def test_guard_allows_unknown_session(self):
        err = guard_cross_session("C:/unknown.cst", "results")
        self.assertIsNone(err)


class GatewayT6DeprecatedAPITests(unittest.TestCase):
    def test_modeler_rejected(self):
        err = guard_execute_vba_entrypoint("modeler")
        self.assertIsNotNone(err)
        self.assertEqual(err["trap"], "T6_deprecated_modeler_api")

    def test_model3d_allowed(self):
        err = guard_execute_vba_entrypoint("model3d")
        self.assertIsNone(err)

    def test_schematic_allowed(self):
        err = guard_execute_vba_entrypoint("schematic")
        self.assertIsNone(err)


class GatewayT8FarfieldQuantityTests(unittest.TestCase):
    def test_realized_gain_passes(self):
        self.assertIsNone(guard_farfield_quantity("Realized Gain"))

    def test_gain_passes(self):
        self.assertIsNone(guard_farfield_quantity("Gain"))

    def test_directivity_passes(self):
        self.assertIsNone(guard_farfield_quantity("Directivity"))

    def test_abs_e_rejected(self):
        err = guard_farfield_quantity("Abs(E)")
        self.assertIsNotNone(err)
        self.assertEqual(err["trap"], "T8_abs_e_not_gain")

    def test_efield_rejected(self):
        err = guard_farfield_quantity("Efield")
        self.assertIsNotNone(err)
        self.assertEqual(err["trap"], "T8_abs_e_not_gain")

    def test_empty_passes_as_realized_gain(self):
        self.assertIsNone(guard_farfield_quantity(""))

    def test_unknown_quantity_rejected(self):
        err = guard_farfield_quantity("SomethingElse")
        self.assertIsNotNone(err)
        self.assertEqual(err["error_type"], "unsupported_quantity")


class GatewayT11FarfieldRunIdTests(unittest.TestCase):
    def test_none_run_id_rejected(self):
        err = guard_farfield_run_id(None)
        self.assertIsNotNone(err)
        self.assertEqual(err["trap"], "T11_farfield_overwrite")

    def test_zero_run_id_allowed(self):
        err = guard_farfield_run_id(0)
        self.assertIsNone(err)

    def test_positive_run_id_allowed(self):
        err = guard_farfield_run_id(5)
        self.assertIsNone(err)


class GatewayT13ChangeParamAnnotationTests(unittest.TestCase):
    def test_success_gets_warning(self):
        result = annotate_change_param_result({"status": "success", "changed": {"g": 23.0}})
        self.assertIn("warning", result)
        self.assertEqual(result["trap_note"], "T13_restore_double_not_model_rebuild")

    def test_error_unchanged(self):
        result = annotate_change_param_result({"status": "error", "message": "oops"})
        self.assertNotIn("warning", result)


class GatewayT14FilterTypeTests(unittest.TestCase):
    def test_0d1d_passes(self):
        self.assertIsNone(guard_result_filter("0D/1D"))

    def test_colormap_passes(self):
        self.assertIsNone(guard_result_filter("colormap"))

    def test_all_passes(self):
        self.assertIsNone(guard_result_filter("all"))

    def test_invalid_rejected(self):
        err = guard_result_filter("wrong_filter")
        self.assertIsNotNone(err)
        self.assertEqual(err["trap"], "T14_tree_items_filter")

    def test_empty_defaults(self):
        self.assertIsNone(guard_result_filter(""))


if __name__ == "__main__":
    unittest.main()
