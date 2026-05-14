# Advanced — P1 Optimization & Architecture

This directory contains content related to P1-level optimization and
architectural design. It is separate from the infrastructure CLI skill
(`skills/cst-runtime-cli/`) to keep the base layer focused and clean.

## Contents

### architecture/
- `leam-like-system-architecture.md` — LEAM-like system architecture design
  for model_intent, Check Solid, and optimization chain
- `phase-c-system-integration-and-portable-mode.md` — System integration,
  portable mode, and skill distribution design

### reference/
- `model-intent-check-solid-research.md` — Research on model_intent and
  Check Solid gate design
- `cst-project-experience-mining.md` — Historical CST project experience
  extraction and knowledge recovery

### validations/
- `showcase-flatness-optimization.md` — Near-boresight flatness optimization
  showcase case study

### planning/
- `current-priority-checklist.md` — Current priority checklist (P1 items)

## Relationship to Infrastructure

- These are **design docs and research**, not production code
- The infrastructure CLI (`skills/cst-runtime-cli/`) provides the building blocks
- This directory defines how to assemble those blocks into an optimization system
- Implementation of these designs will depend on the infra CLI tools
