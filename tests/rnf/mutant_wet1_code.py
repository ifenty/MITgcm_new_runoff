#!/usr/bin/env python3
"""Write the stale-tracer mutant code directory for RUNOFF-043's must-fail demo.

``code_rnfterm_mut_c0`` is lab_sea's ``code/`` plus a copy of
``pkg/rnf/rnf_forcing_surf.F`` whose local arm takes the *initial* tracer
(the literal TRC0 of ``tendency_term_check.py``, which is also the
previous step's tracer when the measured step is the second) instead of
``pTracer(i,j,ks,bi,bj,iTracer)``. Like the other ``code_rnfterm_mut_*``
directories it is git-ignored and never enrolled in a default build. Use:

    python3 tests/rnf/mutant_wet1_code.py
    cd MITgcm/verification && ./experiment_compile.sh lab_sea \
        -mods $PWD/lab_sea/code_rnfterm_mut_c0 -build build_esx_mut_c0 -j 8
    python3 tests/rnf/tendency_term_check.py --use-build build_esx_mut_c0 \
        --case L_unset_wet1 --case L_unset
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tendency_term_check import (ROOT, TRC0, exf_options,  # noqa: E402
                                 write_mods_code)

OLD = ("     &               *pTracer(i,j,ks,bi,bj,iTracer)\n"
       "         ELSE")
NEW = (f"     &               *{TRC0!r} _d 0\n"
       "         ELSE")


def main():
    path = os.path.join(ROOT, "MITgcm", "pkg", "rnf", "rnf_forcing_surf.F")
    with open(path) as fh:
        text = fh.read()
    if text.count(OLD) != 1:
        raise SystemExit(f"{OLD!r} occurs {text.count(OLD)} times in {path}")
    code = write_mods_code("code_rnfterm_mut_c0", {
        "EXF_OPTIONS.h": exf_options(True),
        "rnf_forcing_surf.F": text.replace(OLD, NEW)})
    print(code)


if __name__ == "__main__":
    main()
