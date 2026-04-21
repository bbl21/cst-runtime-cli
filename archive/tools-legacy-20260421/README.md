# Legacy tools archived on 2026-04-21

These scripts were removed from the active `tools/` folder because their roles are now covered by structured runtime CLI tools or by the MCP client/server support scripts that remain in `tools/`.

Archived scripts:

- `cst_cli.py`: early atomic CLI POC; superseded by `uv run python -m cst_runtime`.
- `diag_refresh.py`, `e2e_clean.py`, `e2e_final.py`, `explore_results.py`: bypass/debug scripts from earlier consolidation work.
- `generate_s11_comparison.py`: historical S11 HTML script; superseded by `uv run python -m cst_runtime generate-s11-comparison`.
- `plot_farfield.py`: one-off farfield preview script; superseded by `uv run python -m cst_runtime plot-exported-file` and `plot-farfield-multi`.
- `read_pdf.py`: unrelated utility script; not part of the CST production/runtime tool surface.

Do not call these from production flows. If one is needed for evidence, copy the logic into a structured runtime tool or MCP tool instead of restoring it to `tools/`.
