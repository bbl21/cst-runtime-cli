# cst-runtime-cli

CST Studio Suite CLI infrastructure layer. Provides modeling, simulation,
results reading, and farfield tools through a single CLI entry point.

```powershell
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true
python <skill-root>\scripts\cst_runtime_cli.py list-tools
```

## Quick start

Requires **Python 3.13+**, **uv**, and **CST Studio Suite 2026**.

```powershell
# Auto-detect and configure CST Python libraries
python <skill-root>\scripts\cst_runtime_cli.py health-check --auto-fix true

# Discover available tools
python <skill-root>\scripts\cst_runtime_cli.py list-tools
python <skill-root>\scripts\cst_runtime_cli.py list-pipelines
python <skill-root>\scripts\cst_runtime_cli.py describe-tool --tool change-parameter
```

See [`skills/cst-runtime-cli/SKILL.md`](skills/cst-runtime-cli/SKILL.md) for full documentation.

## What's included

- **105 CLI tools**: session management, modeling, simulation, results, farfield
- **Self-check**: `health-check` diagnoses environment, `install-cst-libraries` configures CST
- **Evidence capture**: `stage-evidence` captures before/after snapshots for verification
- **39 contract tests**: validate JSON output format without starting CST

## License

This repository contains the `cst-runtime-cli` skill package only.
Internal development docs, project planning, and tools are excluded from this public repo.
