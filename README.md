# MITgcm_new_runoff

Planning and design for a new, sparse way to specify runoff forcing in MITgcm (`pkg/exf`), using NetCDF input organized by source.

- `esx/project_profile.md`: decisions, conventions and operations
- `docs/model_contract.md`: NetCDF input and model design contract
- `docs/verification_matrix.md`: oracles and test cases
- `open_issues.md`: open design questions and next tasks (`RUNOFF-*`)
- `tests/mitgcm_oracle.sh`: compile, run and compare a verification experiment in a container

Development uses the [ESX-Team](https://github.com/ifenty/ESX-Team) workflow (installed files under `.claude/`, `devel-loop/`, `tools/esx/`, `esx/`).
- `CLAUDE.md`: project guidance for Claude Code

The MITgcm code changes live in the `new_runoff` branch of [ifenty/MITgcm](https://github.com/ifenty/MITgcm/tree/new_runoff).
