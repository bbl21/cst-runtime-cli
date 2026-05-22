"""gateway.py — CST trap guard layer.

All COM-bound operations must route through here. Maintains a lightweight
state registry per open project to enforce CST-specific safety rules.

Traps guarded (see AGENTS.md + SKILL.md):
  T1  run_id=0 alias        → auto-resolve to real latest run_id
  T2  params-dirty sim      → refuse simulation after param change w/o reopen
  T3  farfield then save    → force save=False after farfield export
  T4  S11 complex ydata     → auto-attach .dB field
  T5  modeler/results mix   → refuse cross-type session
  T6  deprecated modeler    → reject modeler.execute_vba_code, force model3d
  T8  Abs(E) as gain        → reject Abs(E)/Efield in farfield quantity
  T9  pipeline open conflict→ warn on duplicate open
  T10 project_path not file → validate
  T11 farfield overwrite    → require run_id on export
  T12 results before close  → refuse results open while modeler active
  T13 param-readback lie    → annotate change-parameter return
  T14 filter type wrong     → reject invalid get_tree_items filter
  T15 save-before-close     → auto project.save() then close
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .errors import error_response

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_registry: dict[str, "ProjectState"] = {}

_VALID_FILTER_TYPES = frozenset({"0D/1D", "colormap"})
_VALID_GAIN_QUANTITIES = frozenset({"Realized Gain", "Gain", "Directivity"})


# ---------------------------------------------------------------------------
# CstTrapError
# ---------------------------------------------------------------------------
class CstTrapError(Exception):
    """CST-specific runtime trap detected — must stop the operation."""
    def __init__(self, trap_name: str, message: str, suggestion: str = ""):
        super().__init__(message)
        self.trap_name = trap_name
        self.suggestion = suggestion


# ---------------------------------------------------------------------------
# ProjectState
# ---------------------------------------------------------------------------
@dataclass
class ProjectState:
    path: str
    session_type: str = "unknown"   # "modeler" | "results"
    stage: str = "clean"            # "clean" | "params_dirty" | "farfield_exported" | "closed"


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------
def _normalize(path: str) -> str:
    return str(Path(path).expanduser().resolve()).replace("\\", "/")


def _get_state(project_path: str) -> ProjectState | None:
    return _registry.get(_normalize(project_path))


def _ensure_state(project_path: str) -> ProjectState:
    np = _normalize(project_path)
    if np not in _registry:
        _registry[np] = ProjectState(path=np)
    return _registry[np]


def _remove_state(project_path: str) -> None:
    _registry.pop(_normalize(project_path), None)


def _has_session_type(project_path: str, stype: str) -> bool:
    st = _get_state(project_path)
    return st is not None and st.session_type == stype


# ---------------------------------------------------------------------------
# T10 — project_path validation
# ---------------------------------------------------------------------------
def validate_project_path(project_path: str) -> str:
    """Return normalized path; raise if directory instead of .cst file."""
    if not project_path:
        raise ValueError("project_path is required and must point to a .cst file")
    p = Path(project_path).expanduser().resolve()
    if p.is_dir() or p.suffix.lower() not in (".cst", ".prj"):
        raise ValueError(f"project_path must point to a .cst/.prj file, got: {p}")
    return _normalize(project_path)


# ---------------------------------------------------------------------------
# T5 / T9 / T12 — session type tracking
# ---------------------------------------------------------------------------
def on_session_open(project_path: str, session_type: str) -> None:
    """Register an open session. Emit warning (T9) if already open."""
    np = _normalize(project_path)
    existing = _registry.get(np)
    if existing is not None and existing.stage != "closed":
        import warnings
        warnings.warn(
            f"[T9] Project {np} already has an active {existing.session_type} session. "
            "Opening another session may cause conflicts. "
            "Do NOT manually cst-session-open before pipeline tools.",
            UserWarning,
        )
    _registry[np] = ProjectState(path=np, session_type=session_type)


def on_session_close(project_path: str) -> None:
    _remove_state(project_path)


def guard_cross_session(project_path: str, expected_type: str) -> dict[str, Any] | None:
    """T5/T12: refuse if project has wrong session type open. Returns error dict or None."""
    st = _get_state(project_path)
    if st is None:
        return None
    if st.session_type != "unknown" and st.session_type != expected_type:
        return error_response(
            "cross_session_forbidden",
            f"Project has active {st.session_type} session; cannot open {expected_type}. "
            f"Close the {st.session_type} session first.",
            trap="T5_modeler_results_isolation",
            project_path=project_path,
            existing_session=st.session_type,
            requested_session=expected_type,
        )
    return None


# ---------------------------------------------------------------------------
# T2 — params-dirty guard
# ---------------------------------------------------------------------------
def mark_params_dirty(project_path: str) -> None:
    """Call after change_parameter(). Sets stage to params_dirty."""
    st = _ensure_state(project_path)
    st.stage = "params_dirty"


def guard_before_simulation(project_path: str) -> dict[str, Any] | None:
    """T2: refuse simulation if params changed but session not reopened.
    Returns error dict or None."""
    st = _get_state(project_path)
    if st is not None and st.stage == "params_dirty":
        return error_response(
            "params_not_rebuilt",
            "Parameters changed but model NOT rebuilt from disk. "
            "Simulation would use cached old geometry. "
            "Close and reopen the project (or use prepare-experiment pipeline) before simulation.",
            trap="T2_params_not_rebuilt",
            project_path=project_path,
            suggestion="Use prepare-experiment pipeline: close_project → open_project → start_simulation",
        )
    return None


def clear_dirty(project_path: str) -> None:
    """Mark project clean after successful reopen (model reads from disk)."""
    st = _ensure_state(project_path)
    if st.stage == "params_dirty":
        st.stage = "clean"


# ---------------------------------------------------------------------------
# T3 — farfield-exported guard
# ---------------------------------------------------------------------------
def mark_farfield_exported(project_path: str) -> None:
    """Call after farfield export. Prevents save."""
    st = _ensure_state(project_path)
    st.stage = "farfield_exported"


def guard_before_close_save(project_path: str, requested_save: bool) -> tuple[bool, str]:
    """T3: if farfield was exported, force save=False.
    Returns (effective_save, warning_message)."""
    st = _get_state(project_path)
    if st is not None and st.stage == "farfield_exported" and requested_save:
        return False, (
            "[T3] save forced to False: farfield was exported on this session. "
            "Saving after farfield export would corrupt the project file."
        )
    return requested_save, ""


# ---------------------------------------------------------------------------
# T1 — run_id=0 alias
# ---------------------------------------------------------------------------
def resolve_run_id(run_id: int, available_ids: list[int]) -> tuple[int, str]:
    """T1: translate run_id=0 to actual latest run_id.
    Returns (effective_run_id, warning_message)."""
    if run_id != 0:
        return run_id, ""
    positive = sorted(r for r in available_ids if r > 0)
    if not positive:
        return 0, "[T1] No positive run_ids available, falling back to run_id=0"
    latest = positive[-1]
    return latest, (
        f"[T1] run_id=0 translated to {latest} "
        "(run_id=0 is an alias for the latest result in CST)"
    )


# ---------------------------------------------------------------------------
# T4 — S11 complex ydata
# ---------------------------------------------------------------------------
def compute_db(ydata: list[dict[str, float]]) -> list[float]:
    """T4: 20*log10(hypot(real, imag)) for each complex sample."""
    from math import hypot, log10
    return [20.0 * log10(max(hypot(d.get("real", 0), d.get("imag", 0)), 1e-30)) for d in ydata]


def annotate_s11_result(result: dict[str, Any], export_path: str | None = None) -> dict[str, Any]:
    """T4: add .dB series to S11 export."""
    if export_path and "ydata" not in result:
        try:
            import json
            raw = json.loads(Path(export_path).read_text(encoding="utf-8"))
            y = raw.get("ydata", [])
            if y and isinstance(y[0], dict) and "real" in y[0]:
                result["s11_db"] = compute_db(y)
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# T6 — deprecated modeler API
# ---------------------------------------------------------------------------
def guard_execute_vba_entrypoint(entrypoint: str) -> dict[str, Any] | None:
    """T6: reject modeler.execute_vba_code (use model3d in CST 2026)."""
    if entrypoint == "modeler":
        return error_response(
            "deprecated_api",
            "modeler.execute_vba_code is deprecated in CST 2026. Use model3d instead.",
            trap="T6_deprecated_modeler_api",
        )
    return None


# ---------------------------------------------------------------------------
# T8 — Abs(E) as gain evidence
# ---------------------------------------------------------------------------
def guard_farfield_quantity(quantity: str) -> dict[str, Any] | None:
    """T8: reject Abs(E)/Efield as gain quantity."""
    q = (quantity or "").strip()
    qn = q.lower().replace("_", " ").replace("-", " ").replace(".", " ")
    qn = " ".join(qn.split())

    if qn in {"", "realized gain", "realizedgain", "rlzd gain", "rlzdgain", "gain", "abs gain", "absgain",
              "directivity", "abs directivity", "absdirectivity"}:
        return None

    if qn in {"efield", "e field", "electric field", "field", "abs e", "abse", "abs(e)", "abs (e)"}:
        return error_response(
            "not_gain_evidence",
            "Abs(E)/Efield is not a gain metric and cannot be used as dBi gain evidence. "
            "Use Realized Gain, Gain, or Directivity instead.",
            trap="T8_abs_e_not_gain",
            rejected_quantity=q,
        )

    return error_response(
        "unsupported_quantity",
        f"Unsupported farfield quantity '{q}'. Use Realized Gain, Gain, or Directivity.",
    )


# ---------------------------------------------------------------------------
# T11 — farfield overwrite
# ---------------------------------------------------------------------------
def guard_farfield_run_id(run_id: int | None) -> dict[str, Any] | None:
    """T11: farfield export requires explicit run_id to avoid overwrite."""
    if run_id is None:
        return error_response(
            "farfield_run_id_required",
            "Farfield data is overwritten per simulation run. "
            "Provide explicit run_id to preserve historical farfield data.",
            trap="T11_farfield_overwrite",
        )
    return None


# ---------------------------------------------------------------------------
# T13 — change-parameter readback misleading
# ---------------------------------------------------------------------------
def annotate_change_param_result(result: dict[str, Any]) -> dict[str, Any]:
    """T13: warn that parameter table update does NOT mean model rebuilt."""
    if result.get("status") == "success":
        result = {
            **result,
            "warning": (
                "Parameter table updated. Model geometry has NOT been regenerated from disk. "
                "The solver will rebuild from disk on next open. "
                "Close and reopen the project before simulation for changes to take effect."
            ),
            "trap_note": "T13_restore_double_not_model_rebuild",
        }
    return result


# ---------------------------------------------------------------------------
# T14 — get_tree_items filter constraint
# ---------------------------------------------------------------------------
def guard_result_filter(filter_type: str) -> dict[str, Any] | None:
    """T14: cst.results.get_tree_items only supports '0D/1D' and 'colormap'."""
    ft = (filter_type or "0D/1D").strip()
    if ft.lower() == "all":
        return None
    if ft not in _VALID_FILTER_TYPES:
        return error_response(
            "unsupported_filter",
            f"get_tree_items filter '{ft}' not supported. "
            f"Use one of: {sorted(_VALID_FILTER_TYPES)}",
            trap="T14_tree_items_filter",
        )
    return None


# ---------------------------------------------------------------------------
# T15 — save-before-close order
# ---------------------------------------------------------------------------
def guard_close_save_order(project: Any, save: bool) -> None:
    """T15: if save=True, call project.save() BEFORE project.close()."""
    if save and project is not None:
        try:
            project.save()
        except Exception:
            pass  # save failure will be caught by the caller's close logic
