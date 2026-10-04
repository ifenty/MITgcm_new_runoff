# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project goal

Add a new, sparse way to specify runoff forcing in MITgcm, as a new package `pkg/rnf` that feeds `pkg/exf` ([docs/package_design.md](docs/package_design.md)). Runoff is a volumetric water flux, optionally with temperature, salinity (default 0) and any number of passive tracers.

The input is a NetCDF file organized by source: an alphanumeric id, the ocean cells the source feeds, the fraction going into each cell (summing to 1.0), and time series on one shared time axis. This replaces dense per-grid-cell `runoffFile` binaries, which are wasteful at high resolution.

It must work on every MITgcm grid type, and each tile keeps only its own target cells. Phase 1 is 2D surface runoff; 3D runoff via `addMass` comes later.

## Where things are

- **Design and scope:** [esx/project_profile.md](esx/project_profile.md) holds decisions, conventions, contribution rules and operations. [docs/model_contract.md](docs/model_contract.md) is the NetCDF and model design contract. [docs/verification_matrix.md](docs/verification_matrix.md) lists the oracles and test cases. Open design questions and next tasks are the `RUNOFF-*` entries in [open_issues.md](open_issues.md).
- **Code:** `MITgcm/` is a clone of the user's fork `ifenty/MITgcm` (branch `new_runoff`); all code changes go there.
  - Commit to `new_runoff` often and push it to `origin` (the fork).
  - Never commit or push to MITgcm/MITgcm (`upstream`), or to the fork's `master`.
- **Project repo:** this folder is its own git repo (it ignores `MITgcm/`). Commit project and ESX records here and push to `origin main` (github.com/ifenty/MITgcm_new_runoff).
- **Tests:** `tests/mitgcm_oracle.sh <experiment> <input_dir> [-mpi N]` compiles, runs and compares a verification experiment in the `mitgcm:latest` container. Run ESX tools with `/home/ifenty/miniforge3/envs/ecco/bin/python`. The container engine is podman, reached through a `docker` shim; see [docs/code_map.md](docs/code_map.md).

<!-- ESX-TEAM -->
Read [ESX project instructions](esx/project_instructions.md) for the team workflow and project configuration.
<!-- /ESX-TEAM -->
