from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .errors import error_response


_COMMON_CST_PATHS = [
    r"C:\Program Files\CST Studio Suite 2026\AMD64\python_cst_libraries",
    r"C:\Program Files\CST Studio Suite 2025\AMD64\python_cst_libraries",
    r"C:\Program Files (x86)\CST Studio Suite 2026\AMD64\python_cst_libraries",
]


def _probe_path(path_str: str) -> dict[str, Any]:
    p = Path(path_str).expanduser().resolve()
    result: dict[str, Any] = {
        "path": str(p),
        "exists": p.is_dir(),
        "has_interface": False,
        "has_results": False,
        "files_accessible": False,
    }
    if p.is_dir():
        cst_pkg = p / "cst"
        result["has_interface"] = (cst_pkg / "interface").is_dir() if cst_pkg.is_dir() else False
        result["has_results"] = (cst_pkg / "results.py").is_file() if cst_pkg.is_dir() else False
        try:
            next(p.iterdir())
            result["files_accessible"] = True
        except PermissionError:
            pass
    return result


def _scan_registry() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CST AG\CST Studio Suite")
        i = 0
        while True:
            try:
                version = winreg.EnumKey(key, i)
                vk = winreg.OpenKey(key, version)
                try:
                    install_dir, _ = winreg.QueryValueEx(vk, "Installation Directory")
                    py_lib = Path(install_dir) / "AMD64" / "python_cst_libraries"
                    if py_lib.is_dir():
                        info = _probe_path(str(py_lib))
                        info["source"] = f"registry:CST Studio Suite {version}"
                        found.append(info)
                except FileNotFoundError:
                    pass
                winreg.CloseKey(vk)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except (FileNotFoundError, ImportError):
        pass
    return found


def scan_cst_installations() -> dict[str, Any]:
    found: list[dict[str, Any]] = []

    for raw_path in _COMMON_CST_PATHS:
        info = _probe_path(raw_path)
        info["source"] = "common_path"
        if info["exists"]:
            found.append(info)

    found.extend(_scan_registry())

    active_path = _read_active_cst_path()
    return {
        "status": "success",
        "found_count": len(found),
        "installations": found,
        "active_path": active_path,
        "active_valid": bool(active_path and Path(active_path).is_dir()),
    }


def _read_active_cst_path() -> str | None:
    try:
        pyproject = Path.cwd().resolve() / "pyproject.toml"
        if not pyproject.exists():
            pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
        if not pyproject.exists():
            return None
        import tomllib
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        source = data.get("tool", {}).get("uv", {}).get("sources", {}).get("cst-studio-suite-link", {})
        if isinstance(source, dict):
            return source.get("path")
    except Exception:
        pass
    return None


def _write_pyproject_cst_path(cst_path: str) -> dict[str, Any]:
    pyproject = Path.cwd().resolve() / "pyproject.toml"
    if not pyproject.exists():
        pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    if not pyproject.exists():
        return error_response("pyproject_not_found", "No pyproject.toml found in workspace or repo root")

    original = pyproject.read_text(encoding="utf-8")

    toml_path = cst_path.replace("\\", "\\\\")
    entry = f'cst-studio-suite-link = {{ path = "{toml_path}", editable = true }}'

    # 1. 更新 [tool.uv.sources] 中的路径
    entry_start = "cst-studio-suite-link = {"
    idx = original.find(entry_start)
    if idx >= 0:
        line_end = original.find("\n", idx)
        if line_end == -1:
            line_end = len(original)
        new_content = original[:idx] + entry + original[line_end:]
    else:
        heading = "[tool.uv.sources]"
        hidx = original.find(heading)
        if hidx >= 0:
            insert_at = original.find("\n", hidx) + 1
            new_content = original[:insert_at] + entry + "\n" + original[insert_at:]
        else:
            uv_heading = "[tool.uv]"
            uvidx = original.find(uv_heading)
            if uvidx >= 0:
                insert_at = original.find("\n", uvidx) + 1
                new_content = original[:insert_at] + f"\n{heading}\n" + entry + "\n" + original[insert_at:]
            else:
                new_content = original.rstrip() + f"\n\n{uv_heading}\n\n{heading}\n" + entry + "\n"

    if new_content == original:
        return error_response("pyproject_update_failed", "Failed to modify pyproject.toml; check file format")

    # 2. 确保 cst-studio-suite-link 在 [project.dependencies] 中
    dep_name = "cst-studio-suite-link"
    deps_start = "dependencies = ["
    ds = new_content.find(deps_start)
    if ds >= 0:
        de = new_content.find("]", ds)
        if de >= 0 and dep_name not in new_content[ds:de]:
            existing = new_content[ds + len(deps_start):de].strip()
            prefix = f'{dep_name}' if not existing else f', {dep_name}'
            new_content = new_content[:de] + prefix + new_content[de:]

    pyproject.write_text(new_content, encoding="utf-8")
    return {"status": "success", "cst_path": cst_path, "updated_file": str(pyproject)}


def install_cst_libraries(cst_path: str = "", dry_run: bool = False) -> dict[str, Any]:
    scan_result = scan_cst_installations()

    if cst_path:
        target_path = cst_path
        probe = _probe_path(target_path)
        if not probe["exists"]:
            return {
                **error_response("path_not_found", f"CST Python library path does not exist: {target_path}"),
                "scan": scan_result,
            }
    else:
        valid = [inst for inst in scan_result["installations"] if inst["has_interface"] and inst["has_results"]]
        if not valid:
            return {
                **error_response(
                    "cst_not_found",
                    "No CST Studio Suite 2026 Python libraries found. Install CST or provide --cst-path.",
                ),
                "scan": scan_result,
            }
        target_path = valid[0]["path"]

    if dry_run:
        return {
            "status": "success",
            "dry_run": True,
            "target_path": target_path,
            "active_path_matches": target_path == scan_result.get("active_path"),
            "scan": scan_result,
        }

    if target_path == scan_result.get("active_path"):
        verify = _verify_cst_imports(target_path)
        return {
            "status": "success",
            "cst_path": target_path,
            "already_configured": True,
            "pyproject_updated": False,
            "import_verification": verify,
            "scan": scan_result,
        }

    write_result = _write_pyproject_cst_path(target_path)
    if write_result.get("status") == "error":
        return {**write_result, "scan": scan_result}

    verify = _verify_cst_imports(target_path)
    return {
        "status": "success",
        "cst_path": target_path,
        "already_configured": False,
        "pyproject_updated": True,
        "import_verification": verify,
        "scan": scan_result,
    }


def _verify_cst_imports(cst_path: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    sp = str(Path(cst_path).resolve())
    if sp not in sys.path:
        sys.path.insert(0, sp)
    for mod in ("cst", "cst.interface", "cst.results"):
        try:
            __import__(mod)
            results[mod] = "success"
        except Exception as exc:
            results[mod] = f"error: {exc}"
    return results


def _run_uv_cmd(args: list[str], workspace_root: str, timeout: int = 120, label: str = "uv") -> dict[str, Any]:
    try:
        result = subprocess.run(args, cwd=workspace_root, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return {"status": "error", "message": f"{label} failed (exit {result.returncode}):\n{result.stderr.strip()[:500]}"}
        return {"status": "success"}
    except FileNotFoundError:
        return {"status": "error", "message": f"uv not on PATH, cannot run {label}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"{label} timed out after {timeout}s"}
    except Exception as exc:
        return {"status": "error", "message": f"{label} error: {exc}"}


def _record_check(checks: list[dict[str, Any]], remaining: list[dict[str, Any]], name: str, status: str, message: str = "", *, auto_fixed: bool = False, user_action: str = "") -> None:
    item = {"name": name, "status": status, "message": message, "auto_fixed": auto_fixed, "user_action": user_action}
    checks.append(item)
    if status != "pass":
        remaining.append(item)


def health_check(workspace: str = "", auto_fix: bool = True) -> dict[str, Any]:
    from . import workspace as ws_mod
    import platform

    skill_root = ws_mod.skill_root()
    scripts_root = ws_mod.scripts_root()
    ws_info = ws_mod.workspace_status(workspace)

    def _r(name: str, status: str, **kw: Any) -> dict[str, Any]:
        return {"name": name, "status": status, **kw}

    phases: dict[str, Any] = {}
    fixes_applied: list[str] = []

    # ── Phase 1: Workspace + Platform ──
    ws_checks: list[dict[str, Any]] = []

    # 1a. Python version
    py_ok = sys.version_info >= (3, 12)
    ws_checks.append(_r("python_version", "pass" if py_ok else "error",
        version=sys.version, required=">=3.12",
        user_action="Install Python 3.12+" if not py_ok else ""))

    # 1b. uv
    uv_path = shutil.which("uv")
    ws_checks.append(_r("uv", "pass" if uv_path else "warning",
        path=uv_path, user_action="Install uv from https://astral.sh/uv" if not uv_path else ""))

    # 1c. Workspace
    ws_ok = ws_info["workspace_initialized"]
    ws_fixed = False
    if not ws_ok and auto_fix:
        try:
            fix = ws_mod.init_workspace(workspace)
            if fix.get("status") == "success":
                ws_fixed = True
                fixes_applied.append("workspace: initialized workspace")
                ws_info = ws_mod.workspace_status(workspace)
                ws_ok = True
        except Exception:
            pass
    ws_checks.append(_r("workspace", "pass" if ws_ok else "error",
        root=ws_info.get("workspace_root"), marker=ws_info.get("workspace_marker"),
        auto_fixed=ws_fixed,
        user_action="Run init-workspace --workspace <path>" if not ws_ok and not auto_fix else ""))

    # 1d. Skill package
    pkg_ok = (scripts_root / "cst_runtime").exists()
    ws_checks.append(_r("skill_package", "pass" if pkg_ok else "error",
        skill_root=str(skill_root), scripts_root=str(scripts_root)))

    # 1e. stdin
    stdin_info = {"isatty": False, "readable": False}
    for attr in ("isatty", "readable"):
        try:
            stdin_info[attr] = getattr(sys.stdin, attr)()
        except Exception:
            pass
    ws_checks.append(_r("stdin", "success", **stdin_info))

    # 1f. encoding
    ws_checks.append(_r("encoding", "success",
        stdout_encoding=getattr(sys.stdout, "encoding", None),
        stderr_encoding=getattr(sys.stderr, "encoding", None),
        filesystem_encoding=sys.getfilesystemencoding()))

    ws_status = "pass"
    for c in ws_checks:
        if c["status"] == "error":
            ws_status = "error"
            break
        if c["status"] == "warning":
            ws_status = "degraded"
    phases["workspace"] = {"status": ws_status, "checks": ws_checks, "auto_fixed": ws_fixed}

    # ── Phase 2: CST Environment ──
    cst_checks: list[dict[str, Any]] = []

    # 2a. pyproject CST path dependency
    ws_root = Path(str(ws_info.get("workspace_root", "")))
    pyproject_path = ws_root / "pyproject.toml"
    cst_link_path = None
    if pyproject_path.exists():
        try:
            import tomllib
            src = tomllib.loads(pyproject_path.read_text(encoding="utf-8")).get("tool", {}).get("uv", {}).get("sources", {}).get("cst-studio-suite-link", {})
            if isinstance(src, dict):
                cst_link_path = src.get("path")
        except Exception:
            pass
    cst_link_ok = bool(cst_link_path and Path(str(cst_link_path)).is_dir())
    cst_checks.append(_r("pyproject_cst_path", "pass" if cst_link_ok else "info",
        path=cst_link_path))

    # 2b. CST installation scan
    scan = scan_cst_installations()
    cst_found = scan["found_count"] > 0
    cst_valid = any(inst["has_interface"] and inst["has_results"] for inst in scan["installations"])
    cst_configured = scan["active_valid"]

    cst_fixed = False
    if not cst_configured and cst_valid and auto_fix:
        try:
            install_result = install_cst_libraries()
            if install_result.get("status") == "success":
                cst_fixed = True
                fixes_applied.append(f"cst: configured {install_result.get('cst_path', '')}")
                scan = scan_cst_installations()
                cst_configured = True
        except Exception:
            pass

    if not cst_found:
        cst_status, cst_msg = "error", "No CST Studio Suite installation detected"
    elif not cst_valid:
        cst_status, cst_msg = "error", "CST found but Python libraries incomplete"
    elif not cst_configured:
        cst_status, cst_msg = "warning", "CST libraries found but not configured"
    else:
        cst_status, cst_msg = "pass", f"CST libraries at {scan['active_path']}"
    cst_checks.append(_r("cst_libraries", cst_status, message=cst_msg, auto_fixed=cst_fixed))

    # 2c. Import checks
    for mod_name in ("cst_runtime", "cst.interface", "cst.results"):
        try:
            __import__(mod_name)
            cst_checks.append(_r(f"import:{mod_name}", "pass"))
        except Exception as exc:
            cst_checks.append(_r(f"import:{mod_name}", "error", message=str(exc)))

    cst_status_agg = "pass"
    for c in cst_checks:
        if c["status"] == "error":
            cst_status_agg = "error"
            break
        if c["status"] == "warning":
            cst_status_agg = "degraded"
    phases["cst"] = {"status": cst_status_agg, "checks": cst_checks, "auto_fixed": cst_fixed}

    # ── Phase 3: Integration (auto-fix only) ──
    if auto_fix and not any(c["status"] == "error" for c in ws_checks + cst_checks):
        sync_result = _run_uv_cmd(["uv", "sync"], str(ws_root), label="uv sync")
        sync_ok = sync_result["status"] == "success"
        phases["integration"] = {
            "status": "pass" if sync_ok else "error",
            "message": sync_result.get("message", "uv sync completed" if sync_ok else "uv sync failed"),
        }
        if sync_ok:
            first_setup = not (ws_root / ".venv").is_dir() or True
            if first_setup:
                fixes_applied.append("uv_sync: dependencies installed to .venv")
    else:
        phases["integration"] = {"status": "skipped", "message": "uv sync skipped (blocking issues exist or auto_fix=False)"}

    # ── Overall readiness ──
    has_error = any(p.get("status") == "error" for p in phases.values())
    has_warning = any(p.get("status") in ("degraded", "warning") for p in phases.values())
    overall = "blocked" if has_error else ("degraded" if has_warning else "pass")

    return {
        "status": "success",
        "overall": overall,
        "phases": phases,
        "fixes_applied": fixes_applied,
        "workspace": {
            "root": ws_info.get("workspace_root"),
            "initialized": ws_info["workspace_initialized"],
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    }
