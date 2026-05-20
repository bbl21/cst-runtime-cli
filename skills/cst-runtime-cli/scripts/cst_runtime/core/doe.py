from __future__ import annotations

import itertools
import random
from typing import Any


def _two_level_matrix(k: int) -> list[list[int]]:
    """2^(k-p) fractional factorial with foldover for screening.

    For k <= 4: full 2^k factorial.
    For k > 4:  fractional 2^(k-1) with highest-order interaction as generator.
    Ensures at least k+1 rows for effect estimation.
    """
    if k <= 4:
        rows = [list(bits) for bits in itertools.product([-1, 1], repeat=k)]
    else:
        half = k - 1
        base = [list(bits) for bits in itertools.product([-1, 1], repeat=half)]
        rows = []
        for row in base:
            alias = 1
            for j in range(min(half, 3)):
                alias *= row[-(j + 1)]
            rows.append(row + [alias])
    # Add foldover (sign-flipped rows) for clear effect separation
    n_orig = len(rows)
    rows = rows + [[-x for x in r] for r in rows]
    random.Random(42).shuffle(rows)
    return rows[:max(k + 2, n_orig)]


def design_probes(
    parameters: dict[str, dict],
    max_probes: int = 12,
    include_center: bool = True,
) -> dict[str, Any]:
    names = list(parameters.keys())
    k = len(names)
    if k < 1:
        return {"status": "error", "error_type": "no_params", "message": "at least 1 parameter required"}

    matrix = _two_level_matrix(k)
    n_limit = min(max_probes, len(matrix))
    matrix = matrix[:n_limit]

    probes: list[dict[str, float]] = []
    low_vals: dict[str, float] = {}
    high_vals: dict[str, float] = {}
    for name in names:
        pdef = parameters[name]
        low_vals[name] = float(pdef.get("min", pdef.get("low", 0)))
        high_vals[name] = float(pdef.get("max", pdef.get("high", 1)))

    for row in matrix:
        probe: dict[str, float] = {}
        for i, name in enumerate(names):
            val = low_vals[name] if row[i] == -1 else high_vals[name]
            if parameters[name].get("type") == "int":
                val = round(val)
            probe[name] = val
        probes.append(probe)

    # Deduplicate
    seen: set[str] = set()
    unique_probes: list[dict[str, float]] = []
    for p in probes:
        key = str(sorted(p.items()))
        if key not in seen:
            seen.add(key)
            unique_probes.append(p)
    probes = unique_probes

    if include_center:
        center: dict[str, float] = {}
        for name in names:
            val = (low_vals[name] + high_vals[name]) / 2
            if parameters[name].get("type") == "int":
                val = round(val)
            center[name] = val
        # Add center if not duplicate
        ckey = str(sorted(center.items()))
        if ckey not in seen:
            probes.append(center)

    design_label = "fractional-factorial"
    if k <= 4:
        design_label = f"2^{k}"
    elif k <= 6:
        design_label = f"2^({k}-1)"

    return {
        "status": "success",
        "n_probes": len(probes),
        "n_params": k,
        "parameters": names,
        "probes": probes,
        "design": design_label,
        "low": low_vals,
        "high": high_vals,
        "runtime_module": "cst_runtime.core.doe",
    }


def analyze_probes(
    parameters: list[str],
    probes: list[dict],
) -> dict[str, Any]:
    k = len(parameters)
    if k < 1 or len(probes) < 2:
        return {"status": "error", "error_type": "insufficient_data", "message": "at least 2 probes required"}

    valid = [p for p in probes if p.get("value") is not None]
    if len(valid) < 2:
        return {"status": "error", "error_type": "insufficient_data", "message": "at least 2 valid probe results needed"}

    n = len(valid)
    values = [p["value"] for p in valid]
    mean_val = sum(values) / n

    # Infer low/high from data if not provided
    low_vals: dict[str, float] = {}
    high_vals: dict[str, float] = {}
    for name in parameters:
        vals = []
        for p in valid:
            p2 = p.get("params", p)
            v = p2.get(name) if isinstance(p2, dict) else None
            if v is not None:
                vals.append(v)
        if vals:
            low_vals[name] = min(vals)
            high_vals[name] = max(vals)

    # Main effects: contrast-based
    main_effects: dict[str, float] = {}
    for name in parameters:
        lo = low_vals.get(name)
        hi = high_vals.get(name)
        if lo is None or hi is None or lo == hi:
            main_effects[name] = 0.0
            continue
        mid = (lo + hi) / 2
        high_group = []
        low_group = []
        for p in valid:
            p2 = p.get("params", p)
            v = p2.get(name) if isinstance(p2, dict) else None
            if v is None:
                continue
            if v >= mid:
                high_group.append(p["value"])
            else:
                low_group.append(p["value"])
        if high_group and low_group:
            main_effects[name] = round(
                (sum(high_group) / len(high_group)) -
                (sum(low_group) / len(low_group)), 4
            )
        else:
            main_effects[name] = 0.0

    # Two-way interactions
    interactions: dict[str, float] = {}
    if k >= 2:
        for i in range(k):
            for j in range(i + 1, k):
                ni, nj = parameters[i], parameters[j]
                lo_i, hi_i = low_vals.get(ni), high_vals.get(ni)
                lo_j, hi_j = low_vals.get(nj), high_vals.get(nj)
                if any(v is None for v in [lo_i, hi_i, lo_j, hi_j]):
                    continue
                mid_i, mid_j = (lo_i + hi_i) / 2, (lo_j + hi_j) / 2
                sum_int = 0.0
                cnt = 0
                for p in valid:
                    p2 = p.get("params", p)
                    vi = p2.get(ni) if isinstance(p2, dict) else None
                    vj = p2.get(nj) if isinstance(p2, dict) else None
                    if vi is None or vj is None:
                        continue
                    si = 1 if vi >= mid_i else -1
                    sj = 1 if vj >= mid_j else -1
                    sum_int += si * sj * p["value"]
                    cnt += 1
                if cnt > 0:
                    interactions[f"{ni}\u00d7{nj}"] = round(sum_int / cnt, 4)

    # Normalize
    total_abs = sum(abs(v) for v in main_effects.values()) or 1
    normed = {name: round(abs(val) / total_abs, 4) for name, val in main_effects.items()}

    return {
        "status": "success",
        "n_probes": n,
        "mean_value": round(mean_val, 4),
        "main_effects": main_effects,
        "main_effects_normalized": normed,
        "interactions": interactions,
        "top_params": sorted(main_effects, key=lambda n: -abs(main_effects[n])),
        "runtime_module": "cst_runtime.core.doe",
    }
