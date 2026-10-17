# Long-term directions

Record proposed scientific capabilities and research directions. Promote bounded actionable work into open_issues.md.

- **3D and subsurface runoff** (phase 2): route sources with `k > 1` through the core `addMass` (`selectAddFluid`; `MITgcm/model/src/apply_forcing.F`, `integr_continuity.F`), with per-source T and S instead of the domain-wide `temp_addMass` / `salt_addMass`. Phase 1 stores `k` so this isn't designed out. **Brought forward and delivered by RUNOFF-046 (owner decision 2026-10-10):** the generalized route, now the default, puts every target's volume in `addMass` at its own level and its T, S and tracers in as per-level tendencies, the model's domain-wide `temp_addMass`/`salt_addMass` term on the runoff share cancelled; schema 1.1 gives `target_level` as an absolute level. What remains long-term: targets under an ice shelf (RUNOFF-020, which needs an exf variant of isomip).
- **Multiple runoff files** (rivers, glaciers, other): any number of files, each with its own sources and time axis. Phase 1 supports one file, but the data structures must not assume one.
- **Adjoint/TLM qualification**: TAF (`-adm` / `-tlm`) builds of the sparse path, compared against cs32 `input_ad.seaice`, `input_ad.seaice_dynmix` and `input_ad.thsice`.
- **LLC verification**: an LLC experiment with sparse runoff; none exists in `verification/`.
- **Production 2 km dataset**: 50 years of daily runoff at every coastal cell of a global 2 km model; scale and I/O qualification on a cluster.
- **Upstream PR** to MITgcm/MITgcm once phase 1 is qualified, with explicit owner approval.
