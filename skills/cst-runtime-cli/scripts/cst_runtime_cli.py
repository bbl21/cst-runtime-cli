"""Bootstrap CLI entry. Deploys runtime to .cst_runtime/ then delegates.

First run from skill dir:  auto-detects skill path, copies to .cst_runtime/, delegates.
Run from workspace copy:   pass --skill-path <path> for first-time deploy.
Agent production:          directly calls .cst_runtime/cli.py, no skill path needed.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _deploy(skill_scripts: Path, workspace_root: Path) -> None:
    """Copy cst_runtime/ module + references/ + cli.py to workspace."""
    dst = workspace_root / ".cst_runtime"
    dst.mkdir(parents=True, exist_ok=True)

    src_module = skill_scripts / "cst_runtime"
    if dst_module := dst / "cst_runtime":
        if dst_module.exists():
            shutil.rmtree(dst_module)
        shutil.copytree(src_module, dst_module, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    ref_src = skill_scripts.parent / "references"
    if ref_src.exists():
        dst_ref = dst / "references"
        if dst_ref.exists():
            shutil.rmtree(dst_ref)
        shutil.copytree(ref_src, dst_ref, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    (dst / "cli.py").write_text(
        '"""Workspace-local CLI entry."""\n'
        'import sys\nfrom pathlib import Path\n'
        'def main():\n'
        '    root = Path(__file__).resolve().parent\n'
        '    if str(root) not in sys.path: sys.path.insert(0, str(root))\n'
        '    from cst_runtime.cli import main as m\n'
        '    return m()\n'
        'if __name__ == "__main__": raise SystemExit(main())\n',
        encoding="utf-8",
    )


def main() -> int:
    workspace_root = Path.cwd().resolve()
    local_cli = workspace_root / ".cst_runtime" / "cli.py"

    # Determine skill scripts path
    skill_scripts = None
    # --skill-path CLI flag overrides auto-detection
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--skill-path" and i + 1 < len(sys.argv):
            skill_scripts = Path(sys.argv[i + 1]).resolve()
            sys.argv.pop(i + 1)
            sys.argv.pop(i)
            break
    if skill_scripts is None:
        # Auto-detect: when running from skill dir
        candidate = Path(__file__).resolve().parent
        if (candidate / "cst_runtime").is_dir():
            skill_scripts = candidate

    # Deploy if missing or skill path provided
    if skill_scripts and (not local_cli.exists() or "--skill-path" in " ".join(sys.argv)):
        _deploy(skill_scripts, workspace_root)

    # Delegate to workspace-local entry
    sys.path.insert(0, str(local_cli.parent))
    from cst_runtime.cli import main as cli_main
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
