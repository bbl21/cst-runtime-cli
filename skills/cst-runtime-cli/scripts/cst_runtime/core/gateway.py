"""gateway.py — CST trap guard layer.

All COM-bound operations must route through here. Maintains a lightweight
state registry per open project to enforce CST-specific safety rules.

Every guard that returns an error includes:
  cst_raw     — snapshot of relevant COM state at time of failure
  next_action — actionable steps for agent to resolve the error
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    """CST-specific runtime trap detected."""
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
    params_changed: list[str] = None  # list of param names changed this session

    def __post_init__(self):
        if self.params_changed is None:
            self.params_changed = []


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------
def _normalize(path: str) -> str:
    return str(Path(path).expanduser().resolve()).replace("\\", "/")


def _dirty_marker_path(project_path: str) -> Path:
    normalized = _normalize(project_path)
    cst_path = Path(normalized)
    return cst_path.parent / cst_path.stem / ".cst_params_dirty"


def _get_state(project_path: str) -> ProjectState | None:
    state = _registry.get(_normalize(project_path))
    if state is not None:
        return state
    marker = _dirty_marker_path(project_path)
    if marker.exists():
        np = _normalize(project_path)
        state = ProjectState(path=np, stage="params_dirty")
        _registry[np] = state
        return state
    return None


def _ensure_state(project_path: str) -> ProjectState:
    np = _normalize(project_path)
    if np not in _registry:
        _registry[np] = ProjectState(path=np)
    return _registry[np]


def _remove_state(project_path: str) -> None:
    _registry.pop(_normalize(project_path), None)
    _clear_dirty_marker(project_path)


def _clear_dirty_marker(project_path: str) -> None:
    marker = _dirty_marker_path(project_path)
    if marker.exists():
        marker.unlink()


# ---------------------------------------------------------------------------
# T10 — project_path validation
# ---------------------------------------------------------------------------
def validate_project_path(project_path: str) -> str:
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
    _clear_dirty_marker(project_path)  # model rebuilds from disk, dirty state resolved


def _clear_farfield_marker(project_path: str) -> None:
    marker = _farfield_marker_path(project_path)
    if marker.exists():
        marker.unlink()


def on_session_close(project_path: str) -> None:
    _remove_state(project_path)


def guard_cross_session(project_path: str, expected_type: str) -> dict[str, Any] | None:
    st = _get_state(project_path)
    if st is None:
        return None
    if st.session_type != "unknown" and st.session_type != expected_type:
        return error_response(
            "cross_session_forbidden",
            f"Cannot open {expected_type} session: project already has active {st.session_type} session.",
            trap="T5_modeler_results_isolation",
            project_path=project_path,
            cst_raw={
                "existing_session": st.session_type,
                "requested_session": expected_type,
                "registry_stage": st.stage,
                _explain: "modeler and results sessions are independent in CST; mixing produces stale data",
            },
            next_action=f"cst-session-close --project-path {project_path} to release the {st.session_type} session first",
        )
    return None


# ---------------------------------------------------------------------------
# T2 — params-dirty guard
# ---------------------------------------------------------------------------
def mark_params_dirty(project_path: str, param_name: str = "", param_value: Any = None) -> None:
    st = _ensure_state(project_path)
    st.stage = "params_dirty"
    if param_name and param_name not in st.params_changed:
        st.params_changed.append(param_name)
    marker = _dirty_marker_path(project_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("params_dirty", encoding="utf-8")


def guard_before_simulation(project_path: str) -> dict[str, Any] | None:
    st = _get_state(project_path)
    if st is not None and st.stage == "params_dirty":
        dirty_marker = str(_dirty_marker_path(project_path))
        return error_response(
            "params_not_rebuilt",
            f"Parameters changed ({', '.join(st.params_changed) if st.params_changed else 'unknown'}) "
            "but model NOT rebuilt from disk. Simulation would use cached old geometry.",
            trap="T2_params_not_rebuilt",
            project_path=project_path,
            cst_raw={
                "stage": st.stage,
                "params_changed": st.params_changed,
                "dirty_marker": dirty_marker,
                "dirty_marker_exists": Path(dirty_marker).exists(),
                _explain: "CST saves parameter table changes immediately but geometry rebuild only happens on project open",
            },
            next_action=f"cst-session-close --project-path {project_path} --save true, "
                        f"then cst-session-open --project-path {project_path} to force model rebuild from disk",
        )
    return None


def clear_dirty(project_path: str) -> None:
    st = _ensure_state(project_path)
    if st.stage == "params_dirty":
        st.stage = "clean"
        st.params_changed.clear()


# ---------------------------------------------------------------------------
# T3 — farfield-exported guard
# ---------------------------------------------------------------------------
def _farfield_marker_path(project_path: str) -> Path:
    normalized = _normalize(project_path)
    cst_path = Path(normalized)
    return cst_path.parent / cst_path.stem / ".cst_farfield_exported"


def mark_farfield_exported(project_path: str) -> None:
    """Call after farfield export. Prevents save."""
    st = _ensure_state(project_path)
    st.stage = "farfield_exported"
    marker = _farfield_marker_path(project_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("farfield_exported", encoding="utf-8")


def guard_before_close_save(project_path: str, requested_save: bool) -> tuple[bool, str]:
    """T3: if farfield was exported, force save=False."""
    if not requested_save:
        return False, ""

    st = _get_state(project_path)
    if st is not None:
        if st.stage == "farfield_exported":
            return False, (
                "[T3] save forced to False: farfield was exported on this session. "
                "Saving after farfield export would corrupt the project file."
            )
        return requested_save, ""

    # cross-subprocess fallback: check disk marker
    marker = _farfield_marker_path(project_path)
    if marker.exists():
        return False, (
            "[T3] save forced to False: farfield was exported (marker detected). "
            "Saving after farfield export would corrupt the project file."
        )

    return requested_save, ""


# ---------------------------------------------------------------------------
# T1 — run_id=0 alias
# ---------------------------------------------------------------------------
def resolve_run_id(run_id: int, available_ids: list[int]) -> tuple[int, str, dict[str, Any]]:
    """T1: translate run_id=0 to actual latest run_id.
    Returns (effective_run_id, warning_message, cst_raw_info)."""
    if run_id != 0:
        return run_id, "", {}
    positive = sorted(r for r in available_ids if r > 0)
    if not positive:
        return 0, "[T1] No positive run_ids available, falling back to run_id=0", {
            "all_run_ids": available_ids,
            "positive_count": 0,
            _explain: "run_id 0 in CST is an alias for the most recent simulation result",
        }
    latest = positive[-1]
    return latest, (
        f"[T1] Requested run_id=0, resolved to {latest} "
        f"(run_id=0 is always alias for latest result in CST)"
    ), {
        "all_run_ids": available_ids,
        "resolved_to": latest,
        "positive_count": len(positive),
        _explain: "run_id 0 in CST is an alias for the most recent simulation result; "
                  "export_run_results skips run_id 0 to avoid duplicate data",
    }


# ---------------------------------------------------------------------------
# T4 — S11 complex ydata
# ---------------------------------------------------------------------------
def compute_db(ydata: list[dict[str, float]]) -> list[float]:
    from math import hypot, log10
    return [20.0 * log10(max(hypot(d.get("real", 0), d.get("imag", 0)), 1e-30)) for d in ydata]


# ---------------------------------------------------------------------------
# T8 — Abs(E) as gain evidence
# ---------------------------------------------------------------------------
def guard_farfield_quantity(quantity: str) -> dict[str, Any] | None:
    q = (quantity or "").strip()
    qn = q.lower().replace("_", " ").replace("-", " ").replace(".", " ")
    qn = " ".join(qn.split())

    if qn in {"", "realized gain", "realizedgain", "rlzd gain", "rlzdgain", "gain", "abs gain", "absgain",
              "directivity", "abs directivity", "absdirectivity"}:
        return None

    if qn in {"efield", "e field", "electric field", "field", "abs e", "abse", "abs(e)", "abs (e)"}:
        return error_response(
            "not_gain_evidence",
            f"Abs(E)/Efield ({q!r}) is not a gain metric and cannot be reported as dBi.",
            trap="T8_abs_e_not_gain",
            cst_raw={
                "rejected_quantity": q,
                "valid_quantities": sorted(_VALID_GAIN_QUANTITIES),
                _explain: "Abs(E) has units V/m, not dBi; only Realized Gain, Gain, Directivity are gain metrics",
            },
            next_action="Use farfield_plot_mode='Realized Gain', 'Gain', or 'Directivity'",
        )

    return error_response(
        "unsupported_quantity",
        f"Unknown farfield quantity {q!r}. Use one of: {sorted(_VALID_GAIN_QUANTITIES)}.",
        trap="T8_unknown_quantity",
        cst_raw={"rejected_quantity": q, "valid_quantities": sorted(_VALID_GAIN_QUANTITIES)},
        next_action=f"Use one of: {', '.join(sorted(_VALID_GAIN_QUANTITIES))}",
    )


# ---------------------------------------------------------------------------
# T13 — change-parameter readback misleading
# ---------------------------------------------------------------------------
def annotate_change_param_result(result: dict[str, Any], project_path: str = "", param_name: str = "") -> dict[str, Any]:
    if result.get("status") == "success":
        return {
            **result,
            "warning": (
                "Parameter table updated. Model geometry has NOT been regenerated from disk. "
                "The solver will rebuild from disk on next open. "
                "Close and reopen the project before simulation for changes to take effect."
            ),
            "trap_note": "T13_restore_double_not_model_rebuild",
            "cst_raw": {
                "model_rebuilt": False,
                "param_table_updated": True,
                "dirty_marker": str(_dirty_marker_path(project_path)),
                _explain: "StoreDoubleParameter updates the parameter table in memory; "
                          "geometry rebuild happens when solver starts (reads from disk on open)",
            },
            "next_action": f"Use prepare-experiment pipeline to close+save+reopen, "
                           f"then run-experiment to simulate with new values",
        }
    return result


# ---------------------------------------------------------------------------
# T14 — get_tree_items filter constraint
# ---------------------------------------------------------------------------
def guard_result_filter(filter_type: str) -> dict[str, Any] | None:
    ft = (filter_type or "0D/1D").strip()
    if ft.lower() == "all":
        return None
    if ft not in _VALID_FILTER_TYPES:
        return error_response(
            "unsupported_filter",
            f"get_tree_items filter {ft!r} not supported by cst.results module. "
            f"Valid filters: {sorted(_VALID_FILTER_TYPES)}.",
            trap="T14_tree_items_filter",
            cst_raw={
                "rejected_filter": ft,
                "valid_filters": sorted(_VALID_FILTER_TYPES),
                _explain: "cst.results.get_tree_items COM API only accepts '0D/1D' and 'colormap'; "
                          "use 'all' to bypass filtering and get complete tree",
            },
            next_action=f"Use filter_type='0D/1D' for S-parameters and 1D results, "
                        f"or 'colormap' for 2D/3D field results",
        )
    return None


# ---------------------------------------------------------------------------
# T15 — save-before-close order
# ---------------------------------------------------------------------------
def guard_close_save_order(project: Any, save: bool) -> None:
    if save and project is not None:
        try:
            project.save()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# convenience
# ---------------------------------------------------------------------------
_explain = "_explain"
