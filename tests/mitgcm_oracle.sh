#!/bin/bash
#
# Compile, run and check one MITgcm verification experiment against its
# reference output, using the Docker scripts linked into MITgcm/verification.
#
# Usage: tests/mitgcm_oracle.sh <experiment> <input_dir> [-mpi N] [-j N]
#
# Exit status is non-zero if the build fails, the run does not end normally,
# or compare_results.sh reports FAIL. Builds go to build_esx[_mpiN] and runs to
# output_esx_<input_dir>[_mpiN] inside the experiment, so they never clobber
# the default build_docker/output_docker directories.

set -euo pipefail

usage() { echo "Usage: $0 <experiment> <input_dir> [-mpi N] [-j N]" >&2; exit 2; }

[ $# -ge 2 ] || usage
EXP="$1"; INPUT="$2"; shift 2
NPROC=""; JOBS=8
while [ $# -gt 0 ]; do
    case "$1" in
        -mpi) [ $# -ge 2 ] || usage; NPROC="$2"; shift 2 ;;
        -j)   [ $# -ge 2 ] || usage; JOBS="$2"; shift 2 ;;
        *) usage ;;
    esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIF="$ROOT/MITgcm/verification"
[ -d "$VERIF/$EXP/$INPUT" ] || { echo "No such input: $VERIF/$EXP/$INPUT" >&2; exit 2; }

BUILD="build_esx"; OUTPUT="output_esx_${INPUT}"
COMPILE_ARGS=(-j "$JOBS"); RUN_ARGS=()
if [ -n "$NPROC" ]; then
    BUILD="${BUILD}_mpi${NPROC}"; OUTPUT="${OUTPUT}_mpi${NPROC}"
    COMPILE_ARGS+=(-mpi); RUN_ARGS+=(-mpi "$NPROC")
fi

cd "$VERIF"
echo "== compile $EXP ($BUILD)"
./experiment_compile.sh "$EXP" "${COMPILE_ARGS[@]}" -build "$BUILD" </dev/null
echo "== run $EXP/$INPUT ($OUTPUT)"
./experiment_run_no_compile.sh "$EXP" "$INPUT" "${RUN_ARGS[@]}" -build "$BUILD" -output "$OUTPUT" </dev/null
echo "== compare $EXP/$OUTPUT"
./compare_results.sh "$EXP" "$OUTPUT" </dev/null
