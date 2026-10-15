#!/usr/bin/env python3
"""Write the must-fail mutant code directories of RUNOFF-017.

RUNOFF-017 enrols the file-side and configuration refusals of
``tests/rnf/refusal_check.py`` that had no case. The non-vacuity
demonstration is ONE mutant build with the guards of those cases removed,
on which every new case has to fail while it passes on ``build_esx``.

``code_rnfchk_mut_cfg017`` is lab_sea's ``code/`` plus three modified
files of ``pkg/rnf``. The guards it weakens, and nothing else:

1. ``rnf_init_fixed.F`` schema major version: the test
   ``ios.NE.0 .OR. majVer.NE.1`` is made ``.FALSE.`` (``schema_major_2``);
2. ``rnf_init_fixed.F`` missing schema-version attribute: the not-found arm
   no longer counts an error and takes schema 1.0 (``schema_missing``);
3. ``rnf_init_fixed.F`` missing ``mitgcm_grid_ny``: the not-found arm is
   made ``.FALSE.`` (``missing_attribute_ny``);
4. ``rnf_init_fixed.F`` the three ``RNF_NC_ERROR`` calls that follow the
   lookup of the dimensions ``time``, ``source`` and ``target`` are removed
   (``missing_dim_*``);
5. ``rnf_init_fixed.F`` the zero-sources / zero-targets test is made
   ``.FALSE.`` (``no_sources``, ``no_targets``);
6. ``rnf_init_fixed.F`` the ``RNF_NC_ERROR`` calls that follow the lookup of
   ``source_id``, ``target_source`` and ``target_cell`` are removed, and in
   ``rnf_nc_utils.F`` (``RNF_NC_READ_ONE``) the one that follows the lookup
   of the series variable, i.e. ``runoff_flux`` (``missing_variable_*``).
   ``target_fraction`` is left intact: ``missing_variable`` already
   enrols it and must not change;
7. ``rnf_check.F`` the ``addMassFile`` test of the generalized route is
   made ``.FALSE.`` (``generalized_addmassfile``).

The directory is git-ignored (``code_rnfchk_mut_*``). Use:

    python3 tests/rnf/mutant_cfg017_code.py
    cd MITgcm/verification && ./experiment_compile.sh lab_sea \\
        -mods $PWD/lab_sea/code_rnfchk_mut_cfg017 \\
        -build build_esx_mut_cfg017 -j 8
    python3 tests/rnf/refusal_check.py --use-build build_esx_mut_cfg017 \\
        --case schema_major_2 --case schema_missing ...
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tendency_term_check import ROOT, write_mods_code  # noqa: E402

PKG = os.path.join(ROOT, "MITgcm", "pkg", "rnf")

NO_CALL = "C     RUNOFF-017 mutant: guard removed\n"


def dim_call(name):
    return ("      CALL RNF_NC_ERROR( 'RNF_INIT_FIXED',\n"
            f"     &     'looking for the dimension {name}', errNC, myThid )\n")


def var_call(name):
    return ("      CALL RNF_NC_ERROR( 'RNF_INIT_FIXED',\n"
            f"     &     'looking for the required variable {name}',\n"
            "     &     errNC, myThid )\n")


INIT_FIXED = [
    ("      IF ( ios.NE.0 .OR. majVer.NE.1 ) THEN\n",
     "      IF ( .FALSE. ) THEN\n"),
    ("      IF ( .NOT.found ) THEN\n"
     "        WRITE(msgBuf,'(2A)') 'RNF_INIT_FIXED: RNF: the file has no',\n"
     "     &    ' global attribute mitgcm_runoff_schema_version'\n"
     "        CALL PRINT_ERROR( msgBuf, myThid )\n"
     "        errCount = errCount + 1\n"
     "      ELSE\n",
     "      IF ( .NOT.found ) THEN\n"
     "        majVer = 1\n"
     "        minVer = 0\n"
     "      ELSE\n"),
    ("      IF ( .NOT.foundNy ) THEN\n", "      IF ( .FALSE. ) THEN\n"),
    (dim_call("time"), NO_CALL),
    (dim_call("source"), NO_CALL),
    (dim_call("target"), NO_CALL),
    ("      IF ( RNF_nSrcFile.LT.1 .OR. RNF_nTgtFile.LT.1 ) THEN\n",
     "      IF ( .FALSE. ) THEN\n"),
    (var_call("source_id"), NO_CALL),
    (var_call("target_source"), NO_CALL),
    (var_call("target_cell"), NO_CALL),
]

NC_UTILS = [
    ("      errNC = NF_INQ_VARID( fid, varNam(1:iV), varId )\n"
     "      CALL RNF_NC_ERROR( caller, msgBuf, errNC, myThid )\n",
     "      errNC = NF_INQ_VARID( fid, varNam(1:iV), varId )\n"),
]

CHECK = [
    ("        IF ( addMassFile .NE. ' ' ) THEN\n",
     "        IF ( .FALSE. ) THEN\n"),
]

def edit(name, pairs):
    """Return the text of ``pkg/rnf/<name>`` with each pair replaced once."""
    path = os.path.join(PKG, name)
    with open(path) as fh:
        text = fh.read()
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit(f"{old!r} occurs {text.count(old)} times in "
                             f"{path}")
        text = text.replace(old, new)
    return text


def main():
    code = write_mods_code("code_rnfchk_mut_cfg017", {
        "rnf_init_fixed.F": edit("rnf_init_fixed.F", INIT_FIXED),
        "rnf_nc_utils.F": edit("rnf_nc_utils.F", NC_UTILS),
        "rnf_check.F": edit("rnf_check.F", CHECK)})
    print(code)


if __name__ == "__main__":
    main()
