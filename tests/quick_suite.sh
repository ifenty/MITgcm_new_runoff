#!/usr/bin/env bash
# Minimal pkg/rnf smoke suite: about 12 minutes on 4 cores. NOT a qualification
# run; the scientific groups of esx/project.json (verification.scientific_groups)
# remain the evidence of record.
#
# Two lanes run side by side. Lane A uses the serial lab_sea build (build_esx),
# which every serial lab_sea check shares, so it must stay serial. Lane B uses
# separate build_esx_mpiN directories and other experiments, so it can overlap.
#
#   A: package off = baseline | sparse = dense | applied field in time |
#      volume/tracer budget | a few refusals and the valid-file controls
#   B: unit tests | cubed sphere, 4 processes (exch2) | lab_sea tiled, 2 processes
#
# Usage: tests/quick_suite.sh [python]   (default: the mitgcm_rnf conda env)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${1:-/home/ifenty/miniforge3/envs/mitgcm_rnf/bin/python}"
LOG="$(mktemp -d)"
cd "$ROOT"

run() {  # run <lane> <name> <command...>: log, time, record the exit code
    local lane="$1" name="$2"; shift 2
    local t0=$SECONDS
    "$@" > "$LOG/$name.log" 2>&1
    echo "$name $? $((SECONDS - t0))" >> "$LOG/lane_$lane.txt"
}

lane_a() {
    run A lab_sea_baseline   tests/mitgcm_oracle.sh lab_sea input
    run A lab_sea_sp_const   tests/mitgcm_oracle.sh lab_sea input.rnof_sp_const
    run A applied_daily      "$PY" tests/rnf/applied_field_check.py --case lab_sea_daily
    run A budget_lab_sea     "$PY" tests/rnf/budget_check.py --build --case lab_sea --mpi 0
    run A refusal_subset     "$PY" tests/rnf/refusal_check.py \
        --case runofffile --case three_at_once --case positive_control \
        --case cells_equal_dense --case two_sources_one_cell --case ptracer_match
}

lane_b() {
    # test_scale_* asserts a 30 s wall clock, which fails when the model runs share the cores.
    run B unit_tests         "$PY" -m pytest -q tests/runoff -k "not test_scale_"
    run B cs32_sp_mpi4       tests/mitgcm_oracle.sh global_ocean.cs32x15 input.rnof_sp_icedyn -mpi 4
    run B lab_sea_sp_mpi2    tests/mitgcm_oracle.sh lab_sea input.rnof_sp_const -mpi 2
}

: > "$LOG/lane_A.txt"; : > "$LOG/lane_B.txt"
t0=$SECONDS
lane_a & lane_b & wait
echo "logs: $LOG"
cat "$LOG"/lane_A.txt "$LOG"/lane_B.txt | awk '{printf "%-18s %s  %4ds\n", $1, ($2==0?"PASS":"FAIL"), $3; if ($2!=0) bad=1} END {exit bad}'
rc=$?
echo "total $((SECONDS - t0))s  $([ $rc -eq 0 ] && echo ALL PASS || echo FAILURES)"
exit $rc
