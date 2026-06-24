**English** | [中文](README.md)

# CST Runtime CLI

A CLI toolchain and AI agent infrastructure for CST Studio Suite. Provides 113 composable commands covering modeling, simulation, results reading, parameter optimization, and farfield export — with a uniform JSON contract interface and a built-in runtime guard layer that intercepts known CST pitfalls.

The project is also published as AI tool skills, but the toolchain itself is general-purpose: usable standalone, as a skill integration, or as a Python library for custom development.

---

## Capability Map

| Category | Tools | Examples |
|----------|-------|----------|
| **Geometry Modeling** | 42 | `define-brick`, `define-cylinder`, `boolean-subtract`, `change-material`, `transform-shape` |
| **Project Operations** | 25 | `change-parameter`, `define-port`, `define-mesh`, `inspect-project`, `capture-3d-view` |
| **Results** | 11 | `get-1d-result`, `get-2d-result`, `export-run-results`, `list-run-ids`, `generate-report` |
| **Optimization** | 11 | `create-study`, `ask-study`, `tell-study`, `run-probe-phase`, `run-optimization-step` |
| **Session Management** | 7 | `cst-session-open`, `cst-session-close`, `cst-session-quit`, `create-blank-project`, `save-project` |
| **Farfield** | 4 | `export-farfield-grid`, `export-farfield-cut`, `inspect-farfield-monitors`, `inspect-model-view` |
| **Workspace** | 4 | `init-workspace`, `init-task`, `health-check`, `install-cst-libraries` |
| **Project Identity** | 4 | `verify-project-identity`, `infer-run-dir`, `wait-project-unlocked`, `list-open-projects` |
| **Audit** | 3 | `record-stage`, `update-status`, `stage-evidence` |
| **DOE** | 2 | `design-probes`, `analyze-probes` |
| **Run** | 2 | `prepare-run`, `get-run-context` |

Every tool has a JSON Schema definition, validated input, and a uniform response format.

---

## Architecture

### Uniform Contract

All commands share the same I/O contract:

- **Input**: JSON Schema validation, accepted via `--args-file <json>`, `--args-json`, stdin, or direct flags
- **Output**: `{status: "success"|"error", message?, ...}` dict — zero exceptions
- **Audit trail**: Every invocation is logged to `stages/` and `logs/production_chain.md`

### Two-Layer Commands

- **Atomic tools** (113): single-step operations, callable independently.
- **Pipelines**: orchestrated multi-step workflows (`inspect-project`, `prepare-experiment`, `run-experiment`).

Pipelines are provided as reference orchestrations — users are free to design their own workflow strategies using the atomic tools.

### Guard Layer (Gateway)

10+ runtime safety guards that intercept known CST pitfalls:

| Trap | Behavior | Protection |
|------|----------|------------|
| T2 | Simulation with stale parameters | Rejects with `next_action` guidance |
| T3 | Save after farfield export corrupts project | Forces `save=False` |
| T4 | Complex S11 data mistaken for dB | `20*log10(hypot(real,imag))` conversion |
| T5 | Cross-contaminated modeler/results sessions | Rejects cross-session operations |
| T8 | Abs(E) used as gain evidence | Rejects non-gain quantities |
| T13 | `StoreDoubleParameter` skips geometry rebuild | Succeeds with warning |

Each trap carries `cst_raw` context and a `next_action` hint for automatic recovery.

> ⚠️ Guards recognize known patterns only. Complex workflows still require human review at critical checkpoints.

### Dual Session Model

- **Modeler session** (COM read-write via `cst.interface`): modeling, simulation, parameter changes
- **Results session** (read-only via `cst.results`): result extraction, S11/farfield export

Strictly isolated. Close the modeler session after simulation, then open a results session for data extraction.

### Local Report Engine

Fully self-contained HTML/SVG/WebGL reports — zero external JS or CDN dependencies. Supports S11 multi-trace overlays, 3D farfield patterns, 2D heatmaps, iteration timelines, and convergence analysis.

---

## Extensibility

The current 113 tools are not a ceiling. Any CST operation accessible through VBA or COM APIs can be extended as a CLI command through the development kit.

### Code Generator (New VBA Objects)

```powershell
# 1. Write a TOML definition in devkit/tools/vba_defs/
# 2. Run the generator
uv run python devkit/tools/generate_tools.py
# 3. Validates on real CST
# 4. Register in CLI
```

Reference TOML definitions: `devkit/tools/vba_defs/` (10 implementations).

### Manual Enhancement (Existing Tools)

Modify function signatures + synchronize JSON Schema. New parameters carry defaults for backward compatibility.

### Developer References

`devkit/references/` contains: VBA official API reference (1890 lines), CST Python API reference (1377 lines), development workflow guide, and test system documentation.

---

## Quick Start

Prerequisites: CST Studio Suite 2026, Python 3.13+, uv. See `skills/cst-runtime-cli/references/setup_guide.md` for full setup.

```powershell
# Deploy to workspace (one-time)
python bootstrap.py --skill-path <skill-root>\scripts
uv run python -m cst_runtime health-check --auto-fix

# List all available tools
uv run python -m cst_runtime list-tools

# Inspect a project
uv run python -m cst_runtime inspect-project --project-path <project.cst>

# Compose your own workflow
uv run python -m cst_runtime change-parameter --project-path <p.cst> --name g --value 25.0
uv run python -m cst_runtime prepare-experiment --args-file <args.json>
uv run python -m cst_runtime run-experiment --args-file <args.json>
uv run python -m cst_runtime export-run-results --args-file <args.json>
```

---

## Reference Project

`skills/cst-runtime-cli/tests/refs/ref_0/ref_0.cst` — A quad-ridge horn antenna, 8-12 GHz, with a complete modeling history (737 lines of VBA). Used for validating tools and pipelines on real CST. No simulation results included — generated on first run or resolved from workspace cache.

---

## Installation

### Option A: AI Tool Skill

Extract the release archive to your tool's skills directory:

| AI Tool | Path |
|---------|------|
| OpenCode / Cursor / Claude Code | `%USERPROFILE%\.config\opencode\skills\` (or equivalent) |

The extracted structure should include `skills/cst-runtime-cli/` and `skills/cst-runtime-optimization/`.

### Option B: Direct CLI

```powershell
git clone https://github.com/bbl21/cst-runtime-cli.git
cd cst-runtime-cli
python skills/cst-runtime-cli/scripts/bootstrap.py --skill-path skills/cst-runtime-cli/scripts
uv run python -m cst_runtime list-tools
```

### Option C: Python Library

```python
from cst_runtime.core.session import open_project, close_project
from cst_runtime.core.results import get_1d_result
```

---

## Project Structure

```
cst-runtime-cli/
├── devkit/                              # Development toolkit
│   ├── references/                      # VBA/CST API references, dev guide, test docs
│   └── tools/
│       ├── generate_tools.py            # Code generator: TOML → Python
│       ├── vba_defs/                    # TOML definitions (10 reference implementations)
│       └── generated/                   # Generator output (git-ignored)
│
├── skills/
│   ├── cst-runtime-cli/                 # Infrastructure skill
│   │   ├── SKILL.md                     # Agent execution manual
│   │   ├── scripts/
│   │   │   ├── bootstrap.py             # Deployment bootstrap
│   │   │   ├── pyproject.toml           # Package definition
│   │   │   └── cst_runtime/             # All source code
│   │   │       ├── cli/                 # Dispatch layer (dispatch + pipeline orchestration)
│   │   │       ├── core/                # Core modules (session/modeling/simulation/results/farfield/gateway/audit/workspace, 20 modules)
│   │   │       ├── tools/               # Tool layer (10 modules, 113 commands)
│   │   │       ├── render/              # Self-contained HTML/SVG/WebGL reports
│   │   │       └── analysis/            # Farfield parsing and flatness analysis
│   │   ├── references/                  # User documentation
│   │   └── tests/
│   │       ├── refs/ref_0/              # Reference project (quad-ridge horn, 8-12 GHz)
│   │       └── ...                      # Contract tests, architecture invariants, pipeline contracts
│   │
│   └── cst-runtime-optimization/        # Optimization skill (SKILL.md only, no code)
│       └── SKILL.md
│
└── docs/                                # Design documents
```

## License

MIT
