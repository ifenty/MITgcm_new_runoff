"""Tests of :func:`MITgcmutils.runoff.targets.distribute_levels` (RUNOFF-046).

A source spread over a depth range becomes one target entry per wet level of
each of its cells, with an absolute ``target_level`` (schema 1.1). The oracle
is the overlap arithmetic written out by hand on a four-level column with
interfaces at 0, 10, 20, 35 and 60 m: a range of 5-30 m overlaps the three
upper levels by 5, 10 and 10 m, so the shares are exactly 0.2, 0.4 and 0.4;
a bottom partial cell of hFacC 0.4 is wet from 35 to 45 m only. The written
file must pass the checker against the same grid, including R04 (every
level a wet level of the grid), and keep each source's fractions summing
to 1.
"""

import math

import netCDF4
import numpy as np
import pytest

from conftest import write_mds
from MITgcmutils.runoff import check_files
from MITgcmutils.runoff import schema as S
from MITgcmutils.runoff import targets as T
from MITgcmutils.runoff.targets import (BuildError, build_targets, distribute_levels,
                                        write_targets)

D = 0.01
NX = 5
RF = np.array([0.0, -10.0, -20.0, -35.0, -60.0])
DRF = -np.diff(RF)
NR = DRF.size


def column_grid(hf_columns):
    """Lat-lon channel of NX cells in the middle row of three; ``hf_columns``
    maps column i to its hFacC profile (NR values). Other cells are land."""
    lon_e = D * np.arange(NX + 1)
    lat_e = D * np.array([-1.5, -0.5, 0.5, 1.5])
    xg, yg = np.meshgrid(lon_e[:-1], lat_e[:-1])
    xc, yc = np.meshgrid(0.5 * (lon_e[:-1] + lon_e[1:]), 0.5 * (lat_e[:-1] + lat_e[1:]))
    band = np.sin(np.deg2rad(lat_e[1:])) - np.sin(np.deg2rad(lat_e[:-1]))
    rac = 6370.0e3 ** 2 * np.deg2rad(np.diff(lon_e))[None, :] * band[:, None]
    hf = np.zeros((NR, 3, NX))
    for i, prof in hf_columns.items():
        hf[:, 1, i] = prof
    return {"hFacC": hf, "XC": xc, "YC": yc, "XG": xg, "YG": yg, "RAC": rac,
            "RF": RF.reshape(-1, 1, 1), "DRF": DRF.reshape(-1, 1, 1)}


def surface(grid):
    """The 2D grid dict build_targets reads (level 1 of hFacC)."""
    g = {k: grid[k] for k in T._GRID_FIELDS}
    g["hFacC"] = grid["hFacC"][0]
    return g


def levels(grid):
    return {"hFacC": grid["hFacC"], "RF": RF, "DRF": DRF}


def point_sources(grid, cols):
    return [{"source_id": "s{0}".format(i), "lon": float(grid["XC"][1, i]),
             "lat": 0.0} for i in cols]


FULL = [1.0, 1.0, 1.0, 1.0]


def test_overlap_shares_are_the_wet_thickness_in_the_range():
    grid = column_grid({0: FULL, 1: [1.0, 1.0, 1.0, 0.4]})
    t = build_targets(point_sources(grid, [0, 1]), surface(grid))
    d = distribute_levels(t, levels(grid), {"s0": (5.0, 30.0), "s1": ("30 m", "60m")})
    s0 = d.target_source == 0
    assert d.target_level[s0].tolist() == [1, 2, 3]
    assert d.target_fraction[s0].tolist() == pytest.approx([0.2, 0.4, 0.4], abs=1e-15)
    # partial bottom cell: level 4 is wet from 35 to 45 m, so 30-60 m overlaps
    # level 3 by 5 m and level 4 by 10 m
    s1 = d.target_source == 1
    assert d.target_level[s1].tolist() == [3, 4]
    assert d.target_fraction[s1].tolist() == pytest.approx([1 / 3, 2 / 3], abs=1e-15)
    for s in (0, 1):
        assert math.fsum(d.target_fraction[d.target_source == s]) == 1.0
    # every entry keeps its cell's geometry
    assert (d.target_cell[s0] == t.target_cell[0]).all()
    assert (d.target_cell_area[s0] == t.target_cell_area[0]).all()


def test_single_depth_and_unranged_sources():
    grid = column_grid({0: FULL, 2: FULL})
    t = build_targets(point_sources(grid, [0, 2]), surface(grid))
    d = distribute_levels(t, levels(grid), {"s0": (15.0, 15.0)})
    assert d.target_level.tolist() == [2, 1]          # s2 has no range: surface
    assert d.target_fraction.tolist() == [1.0, 1.0]
    # a depth on an interface belongs to the level below it
    d = distribute_levels(t, levels(grid), {"s0": (20.0, 20.0)})
    assert d.target_level.tolist()[0] == 3


def test_range_below_the_floor_is_an_error_or_clipped():
    grid = column_grid({0: [1.0, 1.0, 0.0, 0.0]})      # 20 m deep
    t = build_targets(point_sources(grid, [0]), surface(grid))
    with pytest.raises(BuildError) as e:
        distribute_levels(t, levels(grid), {"s0": (25.0, 30.0)})
    assert "s0" in str(e.value) and "20 m deep" in str(e.value)
    d = distribute_levels(t, levels(grid), {"s0": (25.0, 30.0)}, below_floor="clip")
    assert d.target_level.tolist() == [2] and d.target_fraction.tolist() == [1.0]


def test_ice_shelf_column_and_bad_input_are_errors():
    grid = column_grid({0: FULL})
    t = build_targets(point_sources(grid, [0]), surface(grid))
    shelf = levels(grid)
    shelf["hFacC"] = shelf["hFacC"].copy()
    shelf["hFacC"][0, 1, 0] = 0.0                      # level 1 dry: kTopC > 0
    with pytest.raises(BuildError, match="under an ice shelf"):
        distribute_levels(t, shelf, {"s0": (5.0, 30.0)})
    with pytest.raises(BuildError, match="unknown source_id"):
        distribute_levels(t, levels(grid), {"nope": (0.0, 1.0)})
    with pytest.raises(BuildError, match="0 <= top <= bottom"):
        distribute_levels(t, levels(grid), {"s0": (30.0, 5.0)})
    pcoord = dict(levels(grid), RF=-RF)
    with pytest.raises(BuildError, match="z coordinates"):
        distribute_levels(t, pcoord, {"s0": (5.0, 30.0)})
    with pytest.raises(BuildError, match="below_floor"):
        distribute_levels(t, levels(grid), {}, below_floor="drop")


def test_written_file_is_schema_1_1_and_passes_the_checker(tmp_path):
    grid = column_grid({0: FULL, 1: [1.0, 1.0, 1.0, 0.4], 2: FULL})
    gd = tmp_path / "grid"
    gd.mkdir()
    for key, arr in grid.items():
        write_mds(str(gd / key), arr)
    t = build_targets(point_sources(grid, [0, 1]), str(gd))
    d = distribute_levels(t, str(gd), {"s0": (5.0, 30.0), "s1": (30.0, 60.0)})
    out = write_targets(str(tmp_path / "levels.nc"), d)
    with netCDF4.Dataset(out) as ds:
        assert ds.mitgcm_runoff_schema_version == S.SCHEMA_VERSION_LEVELS
        assert ds.variables["target_level"][:].tolist() == [1, 2, 3, 3, 4]
    r = check_files(out, grid_dir=str(gd), tables_only=True)
    assert r.errors == [] and r.warnings == [], r.format_text()
    # a surface-only table stays schema 1.0 with no target_level
    plain = write_targets(str(tmp_path / "plain.nc"), t)
    with netCDF4.Dataset(plain) as ds:
        assert ds.mitgcm_runoff_schema_version == S.SCHEMA_VERSION
        assert "target_level" not in ds.variables
    # writing the levels into the plain file sets 1.1 there too
    into = write_targets(str(tmp_path / "into.nc"), d, into=plain)
    with netCDF4.Dataset(into) as ds:
        assert ds.mitgcm_runoff_schema_version == S.SCHEMA_VERSION_LEVELS
    # a mutant level beyond the column is what R04 exists for
    with netCDF4.Dataset(out, "a") as ds:
        ds.variables["target_level"][0] = 5                 # beyond Nr = 4
    r = check_files(out, grid_dir=str(gd), tables_only=True)
    assert r.rules("E") == {"R04"}, r.format_text()


def test_command_line_depth_range(tmp_path):
    grid = column_grid({0: FULL, 1: FULL})
    gd = tmp_path / "grid"
    gd.mkdir()
    for key, arr in grid.items():
        write_mds(str(gd / key), arr)
    csv = tmp_path / "src.csv"
    csv.write_text("source_id,lon,lat\ns0,{0!r},0.0\n".format(float(grid["XC"][1, 0])))
    out = str(tmp_path / "cli.nc")
    assert T.main([str(csv), "--grid-dir", str(gd), "-o", out,
                   "--depth-range", "5:30"]) == 0
    with netCDF4.Dataset(out) as ds:
        assert ds.variables["target_level"][:].tolist() == [1, 2, 3]
    assert T.main([str(csv), "--grid-dir", str(gd), "-o", out,
                   "--depth-range", "5-30"]) == 1
