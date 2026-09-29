"""Fixtures for the sparse-runoff checker tests (RUNOFF-001).

Puts the in-repo MITgcmutils on ``sys.path`` and provides helpers to write
example files, edit them in place, and write small MITgcm-style grid output
(``hFacC`` tiled 2 x 2, ``RAC``/``XC``/``YC`` global) for the lab_sea layout.
"""

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "MITgcm" / "utils" / "python" / "MITgcmutils"))

from MITgcmutils.runoff import check_files, write_example  # noqa: E402
from MITgcmutils.runoff.example import NX, NY, lab_sea_grid  # noqa: E402

#: A cell that is land in the test grid and not targeted by the example.
LAND_CELL = 100
#: hFacC levels written to the test grid.
NZ = 2


def modify(path, fn):
    """Open ``path`` in append mode (no masking) and call ``fn(ds)``."""
    import netCDF4
    with netCDF4.Dataset(path, "a") as ds:
        ds.set_auto_mask(False)
        fn(ds)
    return path


def write_mds(base, arr, tiles=None):
    """Write big-endian float64 MITgcm ``.meta``/``.data`` for a (nz,)ny,nx array.

    With ``tiles=(tx, ty)`` the global array is split into tx*ty tile files
    ``base.XXX.YYY.meta/.data`` whose ``dimList`` gives each tile's position.
    """
    arr = np.asarray(arr, dtype=">f8")
    ny, nx = arr.shape[-2:]
    lead = arr.shape[:-2]
    parts = []
    if tiles is None:
        parts.append((base, arr, 0, 0))
    else:
        tx, ty = tiles
        snx, sny = nx // tx, ny // ty
        for bj in range(ty):
            for bi in range(tx):
                sub = arr[..., bj * sny:(bj + 1) * sny, bi * snx:(bi + 1) * snx]
                parts.append(("{0}.{1:03d}.{2:03d}".format(base, bi + 1, bj + 1),
                              sub, bi * snx, bj * sny))
    for fname, sub, i0, j0 in parts:
        sny, snx = sub.shape[-2:]
        dims = [(nx, i0 + 1, i0 + snx), (ny, j0 + 1, j0 + sny)]
        dims += [(n, 1, n) for n in lead[::-1]]
        with open(fname + ".meta", "w") as f:
            f.write(" nDims = [ {0:3d} ];\n".format(len(dims)))
            f.write(" dimList = [\n " + ",\n ".join(
                "{0:5d},{1:5d},{2:5d}".format(*d) for d in dims) + "\n ];\n")
            f.write(" dataprec = [ 'float64' ];\n")
            f.write(" nrecords = [     1 ];\n")
        np.ascontiguousarray(sub).tofile(fname + ".data")


@pytest.fixture
def example(tmp_path):
    """Path of a freshly written default example file."""
    return write_example(str(tmp_path / "runoff.nc"))


@pytest.fixture
def grid_dir(tmp_path):
    """lab_sea-layout grid output: tiled 3D hFacC with one land cell, global 2D rest."""
    d = tmp_path / "grid"
    d.mkdir()
    xc, yc, rac = lab_sea_grid()
    hfac = np.ones((NZ, NY, NX))
    hfac[:, LAND_CELL // NX, LAND_CELL % NX] = 0.0
    hfac[1, 0, 0] = 0.0          # a deeper-level-only land cell: not surface land
    write_mds(str(d / "hFacC"), hfac, tiles=(2, 2))
    write_mds(str(d / "RAC"), rac)
    write_mds(str(d / "XC"), xc)
    write_mds(str(d / "YC"), yc)
    return str(d)


def fired(report, level=None):
    return report.rules(level)
