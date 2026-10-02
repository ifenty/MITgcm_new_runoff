"""Tests of the sparse-runoff target-table builder (RUNOFF-009).

Analytic oracles on synthetic lat-lon grids near the equator: along an
equatorial channel the path distance of the k-th cell is exactly k
great-circle steps and all cells have the same area, so every share is the
kernel formula written out here, independently of the module; a two-width
channel checks the ``W * rA`` weighting; a peninsula between two fjords, with
path lengths summed by hand, checks that distance runs through connected wet
cells and that an enclosed lake gets nothing. The real cs32 grid proves the
``exch2`` neighbour graph topologically: with every cell treated as
wet, a closed cubed sphere of 6 x 32 x 32 quadrilaterals has exactly 12288
edges, every cell has 4 neighbours, and 12 x 32 = 384 edges cross faces.
That all-wet graph, restricted to the wet cells, is then the oracle for cs32
with blank tiles (every grid field 0), including blank tiles on two adjacent
sides of a wet cell; on open one-block grids the ``exch2`` method must equal
the lat-lon neighbours. The grid kind is declared, never inferred: ``latlon``
grids are compared with a brute-force array-neighbour oracle, including the
zonal wrap when blank tiles touch the end columns; lat-lon facets stacked in
the array, cs32 with every mismatched seam hidden by blank tiles, and a block
rotated over the North Pole are exact under ``exch2`` and refused under
``latlon``; without a declaration the default is ``exch2`` only when the grid
directory holds ``data.exch2``, otherwise an error. ``latlon`` needs one
increasing map from column index to XG and from row index to YG, so facets
separated by blank columns and rows are refused too; ``exch2`` refuses a wet
lat-lon row that touches a pole (zero-length edges), where ``latlon`` is exact.
"""

import math
import os
import subprocess
import sys
import time

import netCDF4
import numpy as np
import pytest

from conftest import ROOT, write_mds
from MITgcmutils.runoff import check_files, write_example
from MITgcmutils.runoff import targets as T
from MITgcmutils.runoff.targets import BuildError, build_targets, write_targets

#: Builder distances use this radius; grid areas use MITgcm's rSphere (independent).
R = T.EARTH_RADIUS
RS = 6370.0e3
E1 = math.exp(-1.0)
CS32 = ROOT / "MITgcm" / "verification" / "global_ocean.cs32x15" / "output_esx_input.icedyn"
needs_cs32 = pytest.mark.skipif(not (CS32 / "XG.meta").exists(),
                                reason="cs32 grid output not present")


# ---------------------------------------------------------------------------
# Helpers


def latlon_grid(lon_edges, lat_edges, wet):
    """Grid dict of a lat-lon grid: SW corners, mid-point centers, analytic areas."""
    lon_e = np.asarray(lon_edges, dtype=np.float64)
    lat_e = np.asarray(lat_edges, dtype=np.float64)
    xg, yg = np.meshgrid(lon_e[:-1], lat_e[:-1])
    xc, yc = np.meshgrid(0.5 * (lon_e[:-1] + lon_e[1:]), 0.5 * (lat_e[:-1] + lat_e[1:]))
    band = np.sin(np.deg2rad(lat_e[1:])) - np.sin(np.deg2rad(lat_e[:-1]))
    rac = RS ** 2 * np.deg2rad(np.diff(lon_e))[None, :] * band[:, None]
    return {"hFacC": np.asarray(wet, dtype=np.float64), "XC": xc, "YC": yc,
            "XG": xg, "YG": yg, "RAC": rac}


def make_grid_dir(tmp_path, grid, name="grid"):
    d = tmp_path / name
    d.mkdir()
    for key, arr in grid.items():
        write_mds(str(d / key), arr)
    return str(d)


def gc(lon1, lat1, lon2, lat2):
    """Great-circle distance (m) by the atan2 formula (not the module's haversine)."""
    l1, p1, l2, p2 = (math.radians(v) for v in (lon1, lat1, lon2, lat2))
    dl = l2 - l1
    num = math.hypot(math.cos(p2) * math.sin(dl),
                     math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))
    den = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)
    return R * math.atan2(num, den)


def kernel(kind, r, x):
    """The owner's kernels, written out independently of the module."""
    r = np.asarray(r, dtype=np.float64)
    if kind == "exponential":
        return np.exp(-r / x)
    if kind == "gaussian":
        return np.exp(-(r * r) / (x * x))
    return np.maximum(0.0, 1.0 - r * (1.0 - E1) / x)


def assert_clean(path, grid_dir, tables_only=True):
    """Checker: no errors, no warnings, no R01-R03; tables-only reports S10."""
    r = check_files(path, grid_dir=grid_dir, tables_only=tables_only)
    assert r.errors == [] and r.warnings == [], r.format_text()
    assert not r.rules() & {"R01", "R02", "R03"}, r.format_text()
    assert ("S10" in r.rules("I")) == tables_only, r.format_text()
    return r


def build_checked(tmp_path, sources, grid, name="targets.nc", **kw):
    """Build from grid files (read through rdmds), declared ``latlon`` unless
    stated otherwise, write, and check the output."""
    gd = make_grid_dir(tmp_path, grid, "grid_" + name.replace(".", "_"))
    kw.setdefault("connectivity", "latlon")          # the synthetic grids are lat-lon blocks
    t = build_targets(sources, gd, **kw)
    out = write_targets(str(tmp_path / name), t)
    assert_clean(out, gd)
    return t, out, gd


def write_checked(tmp_path, t, grid, name):
    """Write already-built tables and check them against the grid files."""
    gd = make_grid_dir(tmp_path, grid, "grid_" + name.replace(".", "_"))
    assert_clean(write_targets(str(tmp_path / name), t), gd)


def rows(t, sid):
    """``(cells, fractions, distances)`` of one source."""
    m = t.target_source == t.source_id.index(sid)
    return t.target_cell[m], t.target_fraction[m], t.target_distance[m]


# Equatorial channel: 21 cells of 0.01 degrees in the row centred on the equator.
D = 0.01
CH_NX, CH_I0 = 21, 10
DELTA = R * math.radians(D)          # great-circle step between channel centers


def channel():
    wet = np.zeros((3, CH_NX))
    wet[1] = 1.0
    grid = latlon_grid(D * np.arange(CH_NX + 1), D * np.array([-1.5, -0.5, 0.5, 1.5]), wet)
    assert grid["YC"][1, 0] == 0.0
    src = {"source_id": "src", "lon": float(grid["XC"][1, CH_I0]), "lat": 0.0}
    return grid, src


# ---------------------------------------------------------------------------
# Kernel math on the equatorial channel


@pytest.mark.parametrize("kind", T.SPREAD_TYPES)
def test_kernel_falls_to_one_over_e_at_X(tmp_path, kind):
    grid, src = channel()
    x = 2.0 * DELTA
    t, _, _ = build_checked(tmp_path, [src], grid, emission="spread", spread_type=kind,
                            spread_scale=x, cutoff=5.5 * DELTA)
    cells, f, r = rows(t, "src")
    k = cells % CH_NX - CH_I0
    np.testing.assert_allclose(r, np.abs(k) * DELTA, rtol=1e-12, atol=1e-6)
    reach = 3 if kind == "linear" else 5          # linear: Rcut = 3.16 DELTA < cutoff
    assert k.tolist() == list(range(-reach, reach + 1))
    w = kernel(kind, np.abs(k) * DELTA, x)
    np.testing.assert_allclose(f, w / w.sum(), rtol=1e-12)
    by = dict(zip(k.tolist(), f))
    assert by[0] == f.max()                                  # W(0) is the peak
    assert by[2] / by[0] == pytest.approx(E1, rel=1e-12)     # r = X
    assert by[-2] / by[0] == pytest.approx(E1, rel=1e-12)
    assert math.fsum(f) == pytest.approx(1.0, abs=1e-15)
    s = t.source_id.index("src")
    assert t.source_spread_type[s] == kind and t.source_spread_scale[s] == x


@pytest.mark.parametrize("kind", ["exponential", "gaussian"])
def test_default_cutoff_is_3X(tmp_path, kind):
    grid, src = channel()
    x = 1.9 * DELTA                                  # 3X = 5.7 DELTA
    t, _, _ = build_checked(tmp_path, [src], grid, emission="spread", spread_type=kind,
                            spread_scale=x)
    cells, f, r = rows(t, "src")
    k = cells % CH_NX - CH_I0
    assert k.tolist() == list(range(-5, 6))           # 6 DELTA > 3X although W > 0 there
    assert kernel(kind, 6 * DELTA, x) > 1e-5
    assert t.source_cutoff[0] == pytest.approx(3 * x, rel=1e-15)
    w = kernel(kind, np.abs(k) * DELTA, x)
    np.testing.assert_allclose(f, w / w.sum(), rtol=1e-12)


def test_linear_uses_Rcut_unless_cutoff_is_smaller(tmp_path):
    grid, src = channel()
    x = 2.0 * DELTA
    rcut = x / (1.0 - E1)                            # 3.16 DELTA
    assert kernel("linear", 3 * DELTA, x) > 0 and kernel("linear", 4 * DELTA, x) == 0
    for name, cutoff, reach, eff in (("none.nc", None, 3, rcut),
                                     ("big.nc", 10 * DELTA, 3, rcut),
                                     ("small.nc", 2.5 * DELTA, 2, 2.5 * DELTA)):
        t, _, _ = build_checked(tmp_path, [src], grid, name=name, emission="spread",
                                spread_type="linear", spread_scale=x, cutoff=cutoff)
        cells, f, r = rows(t, "src")
        k = cells % CH_NX - CH_I0
        assert k.tolist() == list(range(-reach, reach + 1)), name
        assert t.source_cutoff[0] == pytest.approx(eff, rel=1e-15)
        w = kernel("linear", np.abs(k) * DELTA, x)
        np.testing.assert_allclose(f, w / w.sum(), rtol=1e-12)


def test_distance_starts_at_zero_at_the_snapped_cell(tmp_path):
    """r = 0 at the snapped cell: an off-centre source spreads exactly as a centred
    one, and its offset is only recorded in source_snap_distance."""
    grid, centred = channel()
    src = dict(centred, lon=centred["lon"] + 0.3 * D)
    d0 = gc(src["lon"], 0.0, grid["XC"][1, CH_I0], 0.0)
    assert d0 == pytest.approx(0.3 * DELTA, rel=1e-9)
    x = 2.0 * DELTA
    kw = dict(emission="spread", spread_type="gaussian", spread_scale=x, cutoff=5.5 * DELTA,
              connectivity="latlon")
    t, _, _ = build_checked(tmp_path, [src], grid, **kw)
    cells, f, r = rows(t, "src")
    k = cells % CH_NX - CH_I0
    assert k.tolist() == list(range(-5, 6))
    np.testing.assert_allclose(r, np.abs(k) * DELTA, rtol=1e-12, atol=1e-6)
    assert r[k.tolist().index(0)] == 0.0
    assert t.source_snap_distance[0] == pytest.approx(d0, rel=1e-9)
    w = kernel("gaussian", np.abs(k) * DELTA, x)          # symmetric about the snapped cell
    np.testing.assert_allclose(f, w / w.sum(), rtol=1e-12)
    ref = build_targets([centred], grid, **kw)
    np.testing.assert_array_equal(f, ref.target_fraction)
    np.testing.assert_array_equal(cells, ref.target_cell)


def test_inland_source_spreads_from_the_snapped_cell(tmp_path):
    """A source 30 km inland with X = 5 km and the default cutoff (15 km) succeeds;
    the kernel peak is at the snapped coastal cell."""
    grid = coast_grid()                       # 0.05-degree cells; land where i < 10
    xc, yc, rac = grid["XC"], grid["YC"], grid["RAC"]
    j0 = 20
    lon = float(xc[j0, 10]) - math.degrees(30000.0 / (R * math.cos(math.radians(yc[j0, 10]))))
    src = {"source_id": "inland", "lon": lon, "lat": float(yc[j0, 10])}
    x = 5000.0
    t, _, _ = build_checked(tmp_path, [src], grid, emission="spread", spread_type="gaussian",
                            spread_scale=x)
    snap = j0 * 40 + 10
    assert t.source_snap_cell.tolist() == [snap]
    assert t.source_snap_distance[0] == pytest.approx(30000.0, rel=1e-4)
    assert t.source_snap_distance[0] > t.source_cutoff[0] == 3 * x     # farther than the cutoff
    cells, f, r = rows(t, "inland")
    by = {c: (fr, d) for c, fr, d in zip(cells.tolist(), f.tolist(), r.tolist())}
    assert by[snap][1] == 0.0 and by[snap][0] == f.max()               # the peak, W(0) = 1
    assert r.max() <= 3 * x and (cells % 40 >= 10).all() and cells.size > 5
    # one cell north of the snapped cell: one meridian step
    north = snap + 40
    dn = gc(xc[j0, 10], yc[j0, 10], xc[j0 + 1, 10], yc[j0 + 1, 10])
    assert by[north][1] == pytest.approx(dn, rel=1e-12)
    assert by[north][0] / by[snap][0] == pytest.approx(
        math.exp(-(dn / x) ** 2) * rac[j0 + 1, 10] / rac[j0, 10], rel=1e-12)
    w = np.exp(-(r / x) ** 2) * rac.ravel()[cells]
    np.testing.assert_allclose(f, w / w.sum(), rtol=1e-12)


# ---------------------------------------------------------------------------
# Area weighting


def test_shares_are_W_times_area(tmp_path):
    """Channel of 10 cells 0.01 deg wide then 5 cells 0.02 deg wide."""
    edges = np.concatenate([D * np.arange(11), 10 * D + 2 * D * np.arange(1, 6)])
    lat_e = D * np.array([-1.5, -0.5, 0.5, 1.5])
    wet = np.zeros((3, edges.size - 1))
    wet[1] = 1.0
    grid = latlon_grid(edges, lat_e, wet)
    src = {"source_id": "src", "lon": float(grid["XC"][1, 9]), "lat": 0.0}   # 9.5 D
    x = 2.1 * DELTA                                                          # 3X = 6.3
    t, _, _ = build_checked(tmp_path, [src], grid, emission="spread",
                            spread_type="exponential", spread_scale=x)
    cells, f, r = rows(t, "src")
    i = cells % (edges.size - 1)
    # centres at 9.5 D (source), 11 D, 13 D, 15 D: path distances by hand, in DELTA
    hand = {9 - k: float(k) for k in range(7)}
    hand.update({10: 1.5, 11: 3.5, 12: 5.5})
    assert i.tolist() == sorted(hand)
    np.testing.assert_allclose(r, [hand[c] * DELTA for c in i.tolist()], rtol=1e-12)
    width = np.where(i < 10, D, 2 * D)
    area = RS ** 2 * np.radians(width) * 2 * math.sin(math.radians(0.5 * D))
    w = np.exp(-r / x) * area
    np.testing.assert_allclose(f, w / w.sum(), rtol=1e-12)
    f10, f8 = f[i.tolist().index(10)], f[i.tolist().index(8)]
    assert f10 / f8 == pytest.approx(2.0 * math.exp(-1.5 / 2.1) / math.exp(-1.0 / 2.1),
                                     rel=1e-12)


# ---------------------------------------------------------------------------
# Connectivity: two fjords around a peninsula, and an enclosed lake

#: (i, j) wet cells: fjord A, fjord B, the channel across their heads, a lake.
FJORD_A = [(1, j) for j in range(4)]
FJORD_B = [(3, j) for j in range(4)]
HEAD = [(i, 4) for i in range(5)]
LAKE = [(6, 1), (6, 2)]
FJ_NX, FJ_NY = 8, 7


def fjords():
    wet = np.zeros((FJ_NY, FJ_NX))
    for i, j in FJORD_A + FJORD_B + HEAD + LAKE:
        wet[j, i] = 1.0
    grid = latlon_grid(D * np.arange(FJ_NX + 1), D * (np.arange(FJ_NY + 1) - 3.5), wet)
    src = {"source_id": "fjordA", "lon": float(grid["XC"][0, 1]),
           "lat": float(grid["YC"][0, 1])}
    return grid, src


def test_distance_runs_through_connected_wet_cells(tmp_path):
    grid, src = fjords()
    xc, yc = grid["XC"], grid["YC"]
    dn = R * math.radians(D)                                    # meridian step
    de = gc(xc[4, 0], yc[4, 0], xc[4, 1], yc[4, 1])            # step along the head row
    hand = {(1, j): j * dn for j in range(4)}
    hand.update({(1, 4): 4 * dn, (0, 4): 4 * dn + de, (2, 4): 4 * dn + de,
                 (3, 4): 4 * dn + 2 * de, (4, 4): 4 * dn + 3 * de,
                 (3, 3): 5 * dn + 2 * de, (3, 2): 6 * dn + 2 * de})
    x = 2.8 * DELTA                                             # cutoff 8.4 DELTA
    t, _, _ = build_checked(tmp_path, [src], grid, emission="spread",
                            spread_type="exponential", spread_scale=x)
    cells, f, r = rows(t, "fjordA")
    got = {(c % FJ_NX, c // FJ_NX): d for c, d in zip(cells.tolist(), r.tolist())}
    assert set(got) == set(hand)
    for ij, d in hand.items():
        assert got[ij] == pytest.approx(d, rel=1e-12), ij
    cutoff = 3 * x
    # Fjord B's lower cells and the lake are within the cutoff as the crow flies...
    for i, j in [(3, 0), (3, 1)] + LAKE:
        assert gc(src["lon"], src["lat"], xc[j, i], yc[j, i]) < cutoff
    # ...but get nothing: fjord B is too far along the water, the lake is unreachable.
    assert 7 * dn + 2 * de > cutoff
    assert not {(3, 0), (3, 1), (6, 1), (6, 2)} & set(got)
    # Around the headland the path is much longer than the great circle.
    assert got[(3, 3)] > 1.9 * gc(src["lon"], src["lat"], xc[3, 3], yc[3, 3])
    area = grid["RAC"].ravel()[cells]
    w = np.exp(-r / x) * area
    np.testing.assert_allclose(f, w / w.sum(), rtol=1e-12)


def test_lake_is_a_separate_component(tmp_path):
    grid, src = fjords()
    g = T.wet_graph(grid, connectivity="latlon")
    assert g.connectivity == "latlon" and not g.periodic
    lake = {j * FJ_NX + i for i, j in LAKE}
    for k, c in enumerate(g.cells.tolist()):
        nb = {int(g.cells[m]) for m in g.neighbours[k] if m >= 0}
        if c in lake:
            assert nb == lake - {c}          # the two lake cells touch each other only
        else:
            assert not nb & lake
    # A source in the lake spreads only inside it.
    lake_src = {"source_id": "lake", "lon": float(grid["XC"][1, 6]),
                "lat": float(grid["YC"][1, 6])}
    t, _, _ = build_checked(tmp_path, [lake_src], grid, emission="spread",
                            spread_type="gaussian", spread_scale=5 * DELTA)
    assert set(rows(t, "lake")[0].tolist()) == lake


# ---------------------------------------------------------------------------
# Snapping


def snap_grid():
    """6 x 5 cells of 0.1 deg at 10E, 20N; columns i <= 2 are land."""
    wet = np.ones((5, 6))
    wet[:, :3] = 0.0
    return latlon_grid(10 + 0.1 * np.arange(7), 20 + 0.1 * np.arange(6), wet)


def test_source_on_land_snaps_to_nearest_wet_cell(tmp_path):
    grid = snap_grid()
    xc, yc = grid["XC"], grid["YC"]
    src = {"source_id": "landlocked", "lon": float(xc[2, 1]), "lat": float(yc[2, 1])}
    t, _, _ = build_checked(tmp_path, [src], grid)
    cells, f, r = rows(t, "landlocked")
    assert cells.tolist() == [2 * 6 + 3] and f.tolist() == [1.0]
    d = gc(src["lon"], src["lat"], xc[2, 3], yc[2, 3])
    assert r[0] == 0.0                                    # r is measured from the snapped cell
    assert t.source_snap_distance[0] == pytest.approx(d, rel=1e-9)
    # the diagonal wet cells are farther
    assert gc(src["lon"], src["lat"], xc[1, 3], yc[1, 3]) > d


def test_snap_beyond_max_distance_is_an_error_naming_the_source(tmp_path):
    grid = snap_grid()
    xc, yc = grid["XC"], grid["YC"]
    far = {"source_id": "landlocked", "lon": float(xc[2, 1]), "lat": float(yc[2, 1])}
    near = {"source_id": "coast", "lon": float(xc[2, 3]), "lat": float(yc[2, 3])}
    d = gc(far["lon"], far["lat"], xc[2, 3], yc[2, 3])
    with pytest.raises(BuildError) as e:
        build_targets([far, near], grid, max_snap_distance="15km")
    msg = str(e.value)
    assert "'landlocked'" in msg and "cell 15 (i=3, j=2" in msg
    assert "{0:.6g} km".format(d / 1e3) in msg and "max_snap_distance = 15 km" in msg
    assert "'coast'" not in msg and len(e.value.errors) == 1
    # the per-source setting overrides the default
    with pytest.raises(BuildError, match="'landlocked'"):
        build_targets([dict(far, max_snap_distance="10000"), near], grid)
    assert build_targets([dict(far, max_snap_distance="25km"), near], grid,
                         max_snap_distance="1km").target_cell.tolist() == [15, 15]


def test_equidistant_source_goes_to_the_lowest_cell_index(tmp_path, monkeypatch):
    grid = snap_grid()
    src = {"source_id": "edge", "lon": float(grid["XG"][2, 4]), "lat": float(grid["YC"][2, 4])}
    a = build_targets([src], grid)
    monkeypatch.setattr(T, "USE_SCIPY", False)
    b = build_targets([src], grid)
    assert a.target_cell.tolist() == b.target_cell.tolist() == [2 * 6 + 3]
    write_checked(tmp_path, b, grid, "tie.nc")


# ---------------------------------------------------------------------------
# Sources: CSV overrides, bad values, edge cases, NetCDF input


def coast_grid():
    """40 x 40 cells of 0.05 deg at the equator, a land block in the west."""
    wet = np.ones((40, 40))
    wet[:, :10] = 0.0
    return latlon_grid(0.05 * np.arange(41), 0.05 * (np.arange(41) - 20), wet)


def write_text(path, text, encoding="utf-8"):
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)
    return str(path)


def test_csv_overrides_take_precedence_and_blanks_use_defaults(tmp_path):
    csv_path = write_text(tmp_path / "s.csv", (
        "source_id,lon,lat,type,emission,spread_type,spread_scale,cutoff,max_snap_distance\n"
        "a,0.8,0.0,river,,,,,\n"
        "b,1.0,0.3,river,pointwise,,,,\n"
        "c,1.2,-0.3,glacier,,exponential,15km,30000,\n"
        "d,1.4,0.5,glacier,,linear,15 km,100km,\n"
        "e,1.6,-0.5,river,,linear,15km,10km,\n"
        "f,0.45,0.0,river,pointwise,,,,60km\n"))
    grid = coast_grid()
    t, out, _ = build_checked(tmp_path, csv_path, grid, emission="spread",
                              spread_type="gaussian", spread_scale="20km",
                              max_snap_distance="5km")
    rcut = 15000.0 / (1.0 - E1)
    expect = {"a": ("spread", "gaussian", 20000.0, 60000.0),
              "b": ("pointwise", "none", None, None),
              "c": ("spread", "exponential", 15000.0, 30000.0),
              "d": ("spread", "linear", 15000.0, rcut),
              "e": ("spread", "linear", 15000.0, 10000.0),
              "f": ("pointwise", "none", None, None)}
    for s, sid in enumerate(t.source_id):
        em, st, x, cut = expect[sid]
        assert (t.source_emission[s], t.source_spread_type[s]) == (em, st), sid
        if x is None:
            assert np.isnan(t.source_spread_scale[s]) and np.isnan(t.source_cutoff[s])
            assert (t.target_source == s).sum() == 1
        else:
            assert t.source_spread_scale[s] == pytest.approx(x, rel=1e-15)
            assert t.source_cutoff[s] == pytest.approx(cut, rel=1e-15)
            assert rows(t, sid)[2].max() <= cut
    # f is 3.5 cells (19 km) from the coast: allowed only by its own 60km setting
    assert t.source_snap_distance[t.source_id.index("f")] > 5000.0
    with netCDF4.Dataset(out) as ds:
        assert list(ds["source_emission"][:]) == [expect[s][0] for s in t.source_id]
        assert ds["source_cutoff"].units == "m"


@pytest.mark.parametrize("column, value, words", [
    ("emission", "diffuse", ["emission", "'diffuse'"]),
    ("spread_type", "gausian", ["spread_type", "'gausian'"]),
    ("spread_scale", "10 miles", ["spread_scale", "10 miles"]),
    ("cutoff", "-5km", ["cutoff", "-5km"]),
    ("max_snap_distance", "abc", ["max_snap_distance", "abc"]),
])
def test_bad_option_values_are_errors_naming_source_and_column(tmp_path, column, value, words):
    csv_path = write_text(tmp_path / "s.csv", "source_id,lon,lat,{0}\nok,1.0,0.0,\n"
                                              "bad_one,1.0,0.2,{1}\n".format(column, value))
    with pytest.raises(BuildError) as e:
        build_targets(csv_path, coast_grid(), emission="spread", spread_type="gaussian",
                      spread_scale="10km")
    msg = str(e.value)
    assert "'bad_one'" in msg and "line 3" in msg and "'ok'" not in msg
    for w in words:
        assert w in msg


def test_spread_needs_type_and_scale(tmp_path):
    src = [{"source_id": "s", "lon": 1.0, "lat": 0.0}]
    with pytest.raises(BuildError, match="needs a spread_type"):
        build_targets(src, coast_grid(), emission="spread", spread_scale="10km")
    with pytest.raises(BuildError, match="needs a spread_scale"):
        build_targets(src, coast_grid(), emission="spread", spread_type="linear")


def test_bad_source_rows_are_all_reported(tmp_path):
    csv_path = write_text(tmp_path / "s.csv", "source_id,lon,lat\n"
                                              "good,1.0,0.0\n"
                                              "has space,1.0,0.0\n"
                                              "good,1.1,0.0\n"
                                              "nolat,1.0,\n"
                                              "pole,1.0,91\n")
    with pytest.raises(BuildError) as e:
        build_targets(csv_path, coast_grid())
    assert len(e.value.errors) == 4
    msg = str(e.value)
    for w in ("'has space'", "also used by", "'nolat'", "lat = ''", "'pole'", "[-90, 90]"):
        assert w in msg


def test_csv_quoting_utf8_and_aliases(tmp_path):
    text = ('source_id,lon,lat,name,type,notes,reference,alt_names\n'
            'jakobshavn,0.8,0.1,Jakobshavn Isbræ,glacier,"Calving front, 2020 position\n'
            'second line","Joughin et al., 2010","Sermeq Kujalleq; Ilulissat Glacier ;'
            'Sermeq Kujalleq"\n'
            'rio,1.2,-0.2,"Río de la Plata, estuary",river,,,\n'
            'short,1.4,0.3,Short Row,river\n')
    csv_path = write_text(tmp_path / "s.csv", text, encoding="utf-8-sig")   # with a BOM
    t, out, _ = build_checked(tmp_path, csv_path, coast_grid())
    assert t.source_id == ["jakobshavn", "rio", "short"]
    with netCDF4.Dataset(out) as ds:
        assert list(ds["source_name"][:]) == ["Jakobshavn Isbræ", "Río de la Plata, estuary",
                                              "Short Row"]
        assert ds["source_notes"][0] == "Calving front, 2020 position\nsecond line"
        assert ds["source_reference"][0] == "Joughin et al., 2010"
        assert list(ds["alias_name"][:]) == ["Sermeq Kujalleq", "Ilulissat Glacier"]
        assert ds["alias_source"][:].tolist() == [0, 0]
        assert "alias_scheme" not in ds.variables
        assert list(ds["source_type"][:]) == ["glacier", "river", "river"]


def test_unknown_csv_column_warns(tmp_path):
    csv_path = write_text(tmp_path / "s.csv", "source_id,lon,lat,spread_scal\ns,1.0,0.0,5km\n")
    with pytest.warns(UserWarning, match="spread_scal"):
        t = build_targets(csv_path, coast_grid())
    assert t.source_emission == ["pointwise"]            # the misspelt column is ignored
    write_checked(tmp_path, t, coast_grid(), "warn.nc")


def test_netcdf_source_table_input(tmp_path):
    """The example file's sources (lab_sea layout) with their names and aliases."""
    ex = write_example(str(tmp_path / "example.nc"))
    wet = np.ones((16, 20))
    wet[0, :5] = 0.0
    grid = latlon_grid(280 + 2.0 * np.arange(21), 46 + 2.0 * np.arange(17), wet)
    t, out, _ = build_checked(tmp_path, ex, grid, max_snap_distance="200km")
    assert t.source_id == ["churchill_labrador", "koksoak", "jakobshavn"]
    # cell = i + 20 j with i = floor((lon-280)/2), j = floor((lat-46)/2)
    assert t.target_cell.tolist() == [69, 125, 234]
    with netCDF4.Dataset(out) as ds:
        assert list(ds["source_name"][:])[2] == "Jakobshavn Isbræ"
        assert list(ds["alias_name"][:]) == ["Grand River", "Sermeq Kujalleq"]
        assert list(ds["alias_scheme"][:]) == ["historical", "Greenlandic"]
        assert ds["source_notes"][0] == "Synthetic example values.\nEnters Lake Melville."


def test_pointwise_one_row_per_source(tmp_path):
    grid = coast_grid()
    xc, yc = grid["XC"], grid["YC"]
    src = [{"source_id": "p{0}".format(k), "lon": float(xc[j, i]) + 0.01,
            "lat": float(yc[j, i]) - 0.01} for k, (i, j) in enumerate(
        [(12, 3), (30, 30), (12, 3), (25, 10)])]
    t, _, _ = build_checked(tmp_path, src, grid)
    assert t.target_source.tolist() == [0, 1, 2, 3]
    assert t.target_fraction.tolist() == [1.0] * 4
    assert t.target_cell.tolist() == [3 * 40 + 12, 30 * 40 + 30, 3 * 40 + 12, 10 * 40 + 25]
    assert t.target_distance.tolist() == [0.0] * 4       # each target is its snapped cell
    assert (t.source_snap_distance > 0).all()
    assert t.target_cell.dtype == np.int32
    assert t.target_cell_area.tolist() == grid["RAC"].ravel()[t.target_cell].tolist()


def test_tiny_scale_leaves_only_the_snapped_cell(tmp_path):
    """A cutoff shorter than one grid step reaches no neighbour: fraction 1 at the
    snapped cell, even for a source off the wet row."""
    grid, src = channel()
    off = dict(src, lat=0.15 * D)            # 0.15 cells off the row, far beyond 3X
    t, _, _ = build_checked(tmp_path, [off], grid, emission="spread", spread_type="gaussian",
                            spread_scale=0.01 * DELTA)
    cells, f, r = rows(t, "src")
    assert cells.tolist() == [CH_NX + CH_I0] and f.tolist() == [1.0] and r.tolist() == [0.0]


# ---------------------------------------------------------------------------
# Neighbour graph: latlon method, zonal wrap, and agreement with the exch2 method


def test_global_latlon_wraps_and_exch2_method_agrees(tmp_path):
    wet = np.ones((10, 36))
    wet[4:6, 10:14] = 0.0
    grid = latlon_grid(10.0 * np.arange(37), 10.0 * np.arange(-5, 6), wet)
    gi = T.wet_graph(grid, connectivity="latlon")
    assert gi.connectivity == "latlon" and gi.periodic
    gc_ = T.wet_graph(grid, connectivity="exch2")
    ea, eb = (set(zip(*[g.cells[e].tolist() for e in g.edges()])) for g in (gi, gc_))
    assert ea == eb
    assert (35, 0) in {(max(a, b) % 36, min(a, b) % 36) for a, b in ea}   # wrap edge
    regional = latlon_grid(10.0 * np.arange(10), 10.0 * np.arange(-5, 6), np.ones((10, 9)))
    assert not T.wet_graph(regional, connectivity="latlon").periodic
    # a spread source at 355E feeds cells on both sides of 0/360
    src = {"source_id": "dateline", "lon": 355.0, "lat": 5.0}
    t, _, _ = build_checked(tmp_path, [src], grid, emission="spread",
                            spread_type="gaussian", spread_scale="800km")
    i = set((rows(t, "dateline")[0] % 36).tolist())
    assert {35, 0, 1} <= i


def test_grid_errors():
    grid, _ = channel()
    cart = dict(grid, YC=grid["YC"] * 1e4)
    with pytest.raises(BuildError, match="Cartesian"):
        build_targets([{"source_id": "s", "lon": 0, "lat": 0}], cart)
    dry = dict(grid, hFacC=np.zeros_like(grid["hFacC"]))
    with pytest.raises(BuildError, match="no wet surface cell"):
        build_targets([{"source_id": "s", "lon": 0, "lat": 0}], dry)
    with pytest.raises(BuildError, match="connectivity"):
        build_targets([{"source_id": "s", "lon": 0, "lat": 0}], grid, connectivity="bfs")


def test_parse_distance():
    assert T.parse_distance("25km") == 25000.0
    assert T.parse_distance(" 25 KM ") == 25000.0
    assert T.parse_distance("2.5e4") == 25000.0
    assert T.parse_distance("25000 m") == 25000.0
    assert T.parse_distance(12) == 12.0
    for bad in ("25 miles", "", "km", True, None):
        with pytest.raises(ValueError):
            T.parse_distance(bad)


def test_fallback_without_scipy_gives_identical_tables(tmp_path, monkeypatch):
    grid, src = fjords()
    kw = dict(emission="spread", spread_type="gaussian", spread_scale=3 * DELTA,
              connectivity="exch2")
    a = build_targets([src], grid, **kw)
    ga = T.wet_graph(grid, connectivity="exch2")
    monkeypatch.setattr(T, "USE_SCIPY", False)
    b = build_targets([src], grid, **kw)
    gb = T.wet_graph(grid, connectivity="exch2")
    for name in ("target_cell", "target_fraction", "target_distance"):
        np.testing.assert_array_equal(getattr(a, name), getattr(b, name))
    np.testing.assert_array_equal(ga.neighbours, gb.neighbours)
    write_checked(tmp_path, b, grid, "fallback.nc")


# ---------------------------------------------------------------------------
# Real cs32 grid


def _face(cells):
    return (np.asarray(cells) % 192) // 32


@needs_cs32
def test_cs32_corner_graph_is_the_closed_cube(monkeypatch):
    """Every cell wet: 12288 edges, degree 4 everywhere, 384 edges across faces."""
    grid = T.read_grid(str(CS32))
    allwet = dict(grid, hFacC=np.ones_like(grid["hFacC"]))
    graphs = []
    for use_scipy in (True, False):
        monkeypatch.setattr(T, "USE_SCIPY", use_scipy)
        graphs.append(T.wet_graph(allwet, connectivity="exch2"))
    g = graphs[0]
    np.testing.assert_array_equal(g.neighbours, graphs[1].neighbours)
    assert g.connectivity == "exch2"
    a, b = g.edges()
    ca, cb = g.cells[a], g.cells[b]
    assert a.size == 12288
    assert np.bincount(g.degree()).tolist() == [0, 0, 0, 0, 6144]
    cross = _face(ca) != _face(cb)
    assert cross.sum() == 384
    # every in-face array neighbour pair is an edge (6 x 2 x 31 x 32 = 11904)
    edges = set(zip(np.minimum(ca, cb).tolist(), np.maximum(ca, cb).tolist()))
    c = np.arange(192 * 32)
    i, j = c % 192, c // 192
    east = c[(i % 32) < 31]
    north = c[j < 31]
    infc = set(zip(east.tolist(), (east + 1).tolist())) | set(
        zip(north.tolist(), (north + 192).tolist()))
    assert len(infc) == 11904 and infc <= edges
    # face-crossing neighbours are about one grid spacing apart
    rac = grid["RAC"].ravel()
    lon, lat = grid["XC"].ravel(), grid["YC"].ravel()
    ratio = [gc(lon[p], lat[p], lon[q], lat[q]) / math.sqrt(0.5 * (rac[p] + rac[q]))
             for p, q in zip(ca[cross].tolist(), cb[cross].tolist())]
    assert 0.8 < min(ratio) and max(ratio) < 1.5
    assert g.diagnostics["synthesized_corners"] == 6     # 2 unstored cube corners x 3 cells
    assert g.diagnostics["unmatched_synthesized_edges"] == 0
    with pytest.raises(BuildError, match="not one regular lat-lon block: XC varies"):
        T.wet_graph(allwet, connectivity="latlon")


@needs_cs32
def test_cs32_geometric_corners_match_the_array_on_every_face():
    """The face-edge corner search, applied to every in-face cell, finds the
    array's corners: SW(i, j), SW(i+1, j), SW(i+1, j+1), SW(i, j+1)."""
    geom = T._Geom(T.read_grid(str(CS32)), T.EARTH_RADIUS)
    vid = T._vertex_ids(geom)
    assert (vid == np.arange(geom.n)).all()                 # 6144 distinct SW corners
    c = np.arange(geom.n)
    infc = c[((c % 192) % 32 < 31) & (c // 192 < 31)]
    assert infc.size == 5766
    ids, synth, _ = T._geometric_corners(geom, vid, infc)
    assert synth == {}
    truth = np.stack([infc, infc + 1, infc + 193, infc + 192], axis=1)
    assert (ids[:, 0] == truth[:, 0]).all() and (ids[:, 2] == truth[:, 2]).all()
    assert (np.sort(ids[:, [1, 3]], axis=1) == np.sort(truth[:, [1, 3]], axis=1)).all()


def _edge_set(g):
    a, b = g.edges()
    return set(zip(g.cells[a].tolist(), g.cells[b].tolist()))


def _array_neighbours(wet, closes=False):
    """Brute-force oracle for one block: (i+1, j) and (i, j+1) pairs of wet cells and,
    when the block closes in longitude, the two end cells of each row."""
    ny, nx = wet.shape
    w = np.asarray(wet).ravel() > 0
    out = {(c, c + 1) for c in range(nx * ny) if c % nx < nx - 1 and w[c] and w[c + 1]}
    out |= {(c, c + nx) for c in range(nx * (ny - 1)) if w[c] and w[c + nx]}
    if closes and nx > 1:
        out |= {(nx * j, nx * j + nx - 1) for j in range(ny) if w[nx * j] and w[nx * j + nx - 1]}
    return out


def _boxes(shape, boxes):
    """Boolean mask of the union of boxes (j0, j1, i0, i1)."""
    m = np.zeros(shape, dtype=bool)
    for j0, j1, i0, i1 in boxes:
        m[j0:j1, i0:i1] = True
    return m


#: Blank-tile cases on cs32: (focus cell (i, j) with two blank edge neighbours or
#: None, land cell (i, j) or None, blank boxes (j0, j1, i0, i1)). 8 x 8 tiles.
_NT, _ET, _NET = (8, 16, 0, 8), (0, 8, 8, 16), (8, 16, 8, 16)
BLANK_CASES = {
    "north": (None, None, [_NT]),
    "east": (None, None, [_ET]),
    "north_and_east": ((7, 7), None, [_NT, _ET]),
    "north_and_east_south_neighbour_land": ((7, 7), (7, 6), [_NT, _ET]),
    "north_east_and_diagonal_sw_cell_land": ((7, 7), (6, 6), [_NT, _ET, _NET]),
    "all_four_sides_of_a_tile": ((15, 15), None, [(16, 24, 8, 16), (8, 16, 16, 24),
                                                  (0, 8, 8, 16), (8, 16, 0, 8)]),
    # across the cube corner at the NE corner of face 1: tiles on faces 2 and 3
    "across_a_cube_corner": ((31, 31), None, [(24, 32, 32, 40), (0, 8, 64, 72)]),
    "across_a_cube_corner_south_neighbour_land": ((31, 31), (31, 30),
                                                  [(24, 32, 32, 40), (0, 8, 64, 72)]),
}


def _cs32_oracle():
    """Edges of the all-wet cs32 graph (the closed cube proven above) and the grid."""
    grid = T.read_grid(str(CS32))
    edges = _edge_set(T.wet_graph(dict(grid, hFacC=np.ones_like(grid["hFacC"])),
                                  connectivity="exch2"))
    assert len(edges) == 12288
    return grid, edges


def _blanked(grid, hfac, blank):
    """Grid with ``hfac`` as wet mask and every field 0 on blank tiles, as rdmds
    returns for tiles absent from MITgcm output."""
    out = {k: v.copy() for k, v in grid.items()}
    out["hFacC"] = hfac.copy()
    for k in out:
        out[k][blank] = 0.0
    return out


@needs_cs32
@pytest.mark.parametrize("case", sorted(BLANK_CASES))
def test_cs32_blank_tiles_give_the_exact_graph(case, monkeypatch):
    """Blank tiles (every grid field 0) beside wet cells: the graph is the all-wet
    graph restricted to the wet cells, also when a cell's SE and NW corners are both
    owned by blank tiles (two adjacent blank sides)."""
    focus, land, boxes = BLANK_CASES[case]
    grid, oracle = _cs32_oracle()
    blank = np.zeros((32, 192), dtype=bool)
    for j0, j1, i0, i1 in boxes:
        blank[j0:j1, i0:i1] = True
    hfac = np.ones((32, 192))
    if land is not None:
        hfac[land[1], land[0]] = 0.0
    test = _blanked(grid, hfac, blank)
    wet = (test["hFacC"] > 0).ravel()
    expect = {e for e in oracle if wet[e[0]] and wet[e[1]]}
    if focus is not None:
        c = focus[0] + 192 * focus[1]
        nb = [b if a == c else a for a, b in oracle if c in (a, b)]
        assert len(nb) == 4 and sum(blank.ravel()[n] for n in nb) == 2
    for use_scipy in (True, False):
        monkeypatch.setattr(T, "USE_SCIPY", use_scipy)
        got = _edge_set(T.wet_graph(test, connectivity="exch2"))
        assert got == expect, (sorted(expect - got), sorted(got - expect))


@needs_cs32
def test_cs32_real_mask_with_all_land_tiles_blank():
    """The real land mask with every all-land 2 x 2 tile blank (348 tiles)."""
    grid, oracle = _cs32_oracle()
    real = (grid["hFacC"] > 0).astype(np.float64)
    blank = np.zeros((32, 192), dtype=bool)
    for j0 in range(0, 32, 2):
        for i0 in range(0, 192, 2):
            if not real[j0:j0 + 2, i0:i0 + 2].any():
                blank[j0:j0 + 2, i0:i0 + 2] = True
    assert blank.sum() // 4 == 348
    wet = (real > 0).ravel()
    expect = {e for e in oracle if wet[e[0]] and wet[e[1]]}
    assert _edge_set(T.wet_graph(_blanked(grid, real, blank), connectivity="exch2")) == expect
    assert expect == _edge_set(T.wet_graph(grid, connectivity="exch2")) and len(expect) == 8438


@pytest.mark.parametrize("dlon, dlat", [(1.0, 1.0), (2.0, 0.5), (0.25, 1.0)])
def test_open_one_block_grid_exch2_method_equals_latlon(dlon, dlat):
    """An open (non-periodic) lat-lon grid at 55N-63N, with square and strongly
    anisotropic cells: the exch2 method gives the lat-lon neighbours, including at
    the north-east corner cell, whose SE, NE and NW corners are no cell's SW corner."""
    nx, ny = 9, 8
    lon_e, lat_e = 10.0 + dlon * np.arange(nx + 1), 55.0 + dlat * np.arange(ny + 1)
    rng = np.random.default_rng(7)
    masks = {"all_wet": np.ones((ny, nx)), "random_land": (rng.random((ny, nx)) > 0.3) * 1.0}
    south_land = np.ones((ny, nx))
    south_land[ny - 2, nx - 1] = 0.0                 # south neighbour of the NE corner cell
    masks["south_of_ne_corner_land"] = south_land
    for name, wet in masks.items():
        grid = latlon_grid(lon_e, lat_e, wet)
        gi = T.wet_graph(grid, connectivity="latlon")
        assert gi.connectivity == "latlon" and not gi.periodic
        assert _edge_set(gi) == _array_neighbours(wet)
        assert _edge_set(T.wet_graph(grid, connectivity="exch2")) == _edge_set(gi), name


@needs_cs32
def test_cs32_exch2_is_exact_when_blank_tiles_hide_every_mismatched_seam():
    """Eight blank 8 x 8 tiles hide every array-adjacent pair of cs32 that is not a
    grid neighbour (the seams between faces 2|3 and 4|5), so nothing in the geometry
    shows that the array is a mosaic. Declared ``exch2`` the graph is exact; the array
    neighbours alone miss 192 cross-face edges; declared ``latlon`` is refused."""
    grid, oracle = _cs32_oracle()
    tiles = [(0, 8), (0, 16), (1, 7), (1, 15), (2, 8), (2, 15), (3, 8), (3, 15)]
    blank = _boxes((32, 192), [(8 * r, 8 * r + 8, 8 * c, 8 * c + 8) for r, c in tiles])
    test = _blanked(grid, np.ones((32, 192)), blank)
    wet = (test["hFacC"] > 0).ravel()
    expect = {e for e in oracle if wet[e[0]] and wet[e[1]]}
    assert _edge_set(T.wet_graph(test, connectivity="exch2")) == expect
    by_array = _array_neighbours(test["hFacC"])
    assert by_array < expect and len(expect - by_array) == 192
    with pytest.raises(BuildError, match="not one regular lat-lon block"):
        T.wet_graph(test, connectivity="latlon")


def test_latlon_regular_grids_give_the_array_neighbours():
    """Regular lat-lon blocks declared ``latlon``: pole to pole, stretched in
    latitude, regional, and a single row, against the brute-force oracle."""
    lat_e = np.cumsum(np.r_[-78.0, 3.0 - 2.4 * np.exp(-((np.arange(60) - 30) / 9.0) ** 2)])
    assert lat_e.max() < 90
    cases = [("pole to pole, 4 deg", np.arange(0, 364, 4.0), np.arange(-90, 94, 4.0), True),
             ("stretched in y from 0.6 to 3 deg", np.arange(0, 362, 2.0), lat_e, True),
             ("regional 20 x 16", 280 + 2.0 * np.arange(21), 46 + 2.0 * np.arange(17), False),
             ("single row", np.arange(0, 41, 1.0), np.array([10.0, 11.0]), False),
             ("359 of 360 degrees", np.arange(0, 360, 1.0), np.arange(-5, 6, 1.0), False)]
    for name, lon_e, lat_e_, closes in cases:
        wet = np.ones((len(lat_e_) - 1, len(lon_e) - 1))
        g = T.wet_graph(latlon_grid(lon_e, lat_e_, wet), connectivity="latlon")
        assert g.connectivity == "latlon" and g.periodic == closes, name
        assert _edge_set(g) == _array_neighbours(wet, closes), name
    # polar rows of a pole-to-pole grid: east, west (wrapped at the ends) and one meridional
    g = T.wet_graph(latlon_grid(10.0 * np.arange(37), 10.0 * np.arange(-9, 10),
                                np.ones((18, 36))), connectivity="latlon")
    deg = g.degree().reshape(18, 36)
    assert (deg[[0, 17]] == 3).all() and (deg[1:17] == 4).all()
    assert len(_edge_set(g)) == 18 * 36 + 17 * 36
    assert (17 * 36, 17 * 36 + 35) in _edge_set(g)


#: Blank tiles (every field 0) on a global 90 x 40 lat-lon grid: (j0, j1, i0, i1).
END_COLUMN_CASES = {
    "interior_tile": (16, 24, 30, 45),
    "whole_southern_tile_row": (0, 8, 0, 90),
    "tile_at_the_first_columns": (0, 8, 0, 15),
    "tile_at_the_last_columns": (32, 40, 75, 90),
}


@pytest.mark.parametrize("case", sorted(END_COLUMN_CASES))
def test_latlon_wrap_survives_blank_tiles_at_the_end_columns(case):
    """A blank tile touching the first or last column removes the zonal wrap only in
    its own rows: the other 32 rows keep the link between their end cells."""
    wet = np.ones((40, 90))
    base = latlon_grid(np.arange(0, 364, 4.0), np.arange(-80, 84, 4.0), wet)
    blank = _boxes((40, 90), [END_COLUMN_CASES[case]])
    grid = _blanked(base, wet, blank)
    expect = _array_neighbours(~blank, closes=True)
    wrap = {e for e in expect if e[1] - e[0] == 89}
    assert len(wrap) == (40 if case == "interior_tile" else 32)
    g = T.wet_graph(grid, connectivity="latlon")
    assert g.periodic and _edge_set(g) == expect
    assert _edge_set(T.wet_graph(grid, connectivity="exch2")) == expect


def stacked_facets():
    """Two 12 x 10 lat-lon facets stacked in y as in the LLC compact layout:
    A covers 0-60E (rows 0-9), B covers 60E-120E (rows 10-19); A's east edge is B's
    west edge. Returns the grid and the seam pairs."""
    lat_e = np.arange(-25, 26, 5.0)
    a = latlon_grid(np.arange(0, 61, 5.0), lat_e, np.ones((10, 12)))
    b = latlon_grid(np.arange(60, 121, 5.0), lat_e, np.ones((10, 12)))
    seam = {(11 + 12 * j, 12 * (j + 10)) for j in range(10)}
    return {k: np.vstack([a[k], b[k]]) for k in a}, seam


#: Blank boxes on the stacked facets, and the valid columns they leave.
STACKED_CASES = {
    "all_valid": [],
    "overlapping_columns": [(0, 10, 0, 4), (10, 20, 8, 12)],        # A 4-11, B 0-7
    "disjoint_columns": [(0, 10, 0, 6), (10, 20, 6, 12)],           # A 6-11, B 0-5
    # A columns 8-11, rows 0-7; B columns 0-3, rows 2-9 of its block: blank columns
    # 4-7 and blank rows 8-11 lie between the two valid parts
    "separated_by_blank_columns_and_rows": [(0, 20, 4, 8), (0, 10, 0, 4), (10, 20, 8, 12),
                                            (8, 12, 0, 12)],
}


@pytest.mark.parametrize("case", sorted(STACKED_CASES))
def test_stacked_latlon_facets_are_exact_under_exch2_and_refused_under_latlon(case):
    """Stacked lat-lon facets are an exch2 layout: declared ``exch2`` the graph has
    each facet's array neighbours plus the seam links; declared ``latlon`` it is
    refused, also when the valid cells of the two facets lie in disjoint array
    columns, where XC depends only on i and only the shared-edge test fails, and when
    blank columns and rows separate them, where XG restarts across the blank columns."""
    grid, seam = stacked_facets()
    blank = _boxes((20, 12), STACKED_CASES[case])
    grid = _blanked(grid, np.ones((20, 12)), blank)
    valid = ~blank
    none = np.zeros((10, 12), dtype=bool)
    expect = (_array_neighbours(np.vstack([valid[:10], none]))
              | _array_neighbours(np.vstack([none, valid[10:]]))
              | {e for e in seam if valid.ravel()[e[0]] and valid.ravel()[e[1]]})
    assert _edge_set(T.wet_graph(grid, connectivity="exch2")) == expect
    if case == "disjoint_columns":
        assert len(expect) == 218 and len(expect & seam) == 10
        assert T._latlon_problem(T._Geom(grid, R)).startswith("column i = 5 ends at 90")
    if case == "separated_by_blank_columns_and_rows":
        assert len(expect) == 110 and len(expect & seam) == 6
        problem = T._latlon_problem(T._Geom(grid, R))
        assert problem.startswith("column i = 3 ends at 80 degrees (2 XC - XG) and the next "
                                  "column with valid cells, 8, starts at 40 (XG)")
        assert "4 blank column(s)" in problem and "not one increasing function" in problem
    with pytest.raises(BuildError, match="not one regular lat-lon block"):
        T.wet_graph(grid, connectivity="latlon")


def test_latlon_needs_one_increasing_map_from_index_to_edge():
    """Blank bands inside a true lat-lon grid are accepted, and the graph is exact;
    two blocks whose XG or YG restarts, or that leave no room for the blank columns
    or rows between them, are refused."""
    wet = np.ones((40, 90))
    base = latlon_grid(np.arange(0, 364, 4.0), np.arange(-80, 84, 4.0), wet)
    blank = _boxes((40, 90), [(0, 40, 30, 45), (16, 24, 0, 90)])     # a column band, a row band
    g = T.wet_graph(_blanked(base, wet, blank), connectivity="latlon")
    assert g.periodic and _edge_set(g) == _array_neighbours(~blank, closes=True)
    blank = _boxes((40, 90), [(0, 40, 0, 6)])                        # the first 6 columns
    g = T.wet_graph(_blanked(base, wet, blank), connectivity="latlon")
    assert not g.periodic and _edge_set(g) == _array_neighbours(~blank)
    # stretched latitudes (0.6 to 3 degrees) with the finest rows blank
    lat_e = np.cumsum(np.r_[-78.0, 3.0 - 2.4 * np.exp(-((np.arange(60) - 30) / 9.0) ** 2)])
    wet = np.ones((60, 20))
    blank = _boxes((60, 20), [(20, 41, 0, 20)])
    g = T.wet_graph(_blanked(latlon_grid(np.arange(0, 41, 2.0), lat_e, wet), wet, blank),
                    connectivity="latlon")
    assert _edge_set(g) == _array_neighbours(~blank)

    def problem(lon_a, lat_a, lon_b, lat_b, stack):
        """Two 4 x 4 blocks with 2 blank columns (or rows) between them in the array."""
        a = latlon_grid(lon_a, lat_a, np.ones((4, 4)))
        b = latlon_grid(lon_b, lat_b, np.ones((4, 4)))
        zero = {k: np.zeros((4, 2) if stack == "x" else (2, 4)) for k in a}
        join = np.hstack if stack == "x" else np.vstack
        return T._latlon_problem(T._Geom({k: join([a[k], zero[k], b[k]]) for k in a}, R))

    x, y = np.arange(5.0), 40.0 + np.arange(5.0)
    assert problem(x, y, 6.0 + x, y, "x") is None                 # one grid, 2 blank columns
    assert problem(x, y, x, 46.0 + np.arange(5.0), "y") is None    # one grid, 2 blank rows
    assert "XG is not one increasing function" in problem(x, y, x - 10.0, y, "x")      # restart
    assert "does not leave room for the 2 blank column(s)" in problem(x, y, 4.0 + x, y, "x")
    assert "does not leave room for the 2 blank column(s)" in problem(x, y, 30.0 + x, y, "x")
    assert "YG is not one increasing function" in problem(x, y, x, y, "y")             # restart
    # a closed 360-degree span with blank columns at the array ends cannot be one grid
    ring = latlon_grid(np.arange(0, 364, 4.0), np.arange(0, 9, 4.0), np.ones((2, 90)))
    ends = {k: np.hstack([np.zeros((2, 2)), v]) for k, v in ring.items()}
    assert "leaves no room for the 2 column(s)" in T._latlon_problem(T._Geom(ends, R))


def test_exch2_refuses_latlon_rows_that_touch_a_pole(tmp_path):
    """A wet row of a lat-lon grid touching a pole has zero-length edges, which the
    corner method can't match: ``exch2`` stops, naming the cell and pointing to
    ``latlon``, which is exact there. With the polar rows dry ``exch2`` is exact."""
    p2p = latlon_grid(np.arange(0, 364, 4.0), np.arange(-90, 94, 4.0), np.ones((45, 90)))
    with pytest.raises(BuildError) as e:
        T.wet_graph(p2p, connectivity="exch2")
    msg = str(e.value)
    assert "cell 0 (i=0, j=0" in msg and "zero-length edge" in msg
    assert "also the SW corner of its east array neighbour" in msg
    assert "connectivity='latlon' (--connectivity latlon)" in msg and "data.exch2" in msg
    north = {k: v.copy() for k, v in p2p.items()}
    north["hFacC"][0:3] = 0.0                          # only the north polar row touches a pole
    with pytest.raises(BuildError) as e:
        T.wet_graph(north, connectivity="exch2")
    assert "cell 3960 (i=0, j=44" in str(e.value) and "collapses onto the north pole" in str(e.value)
    g = T.wet_graph(north, connectivity="latlon")
    assert _edge_set(g) == _array_neighbours(north["hFacC"], closes=True) and len(_edge_set(g)) == 7470
    dry = {k: v.copy() for k, v in p2p.items()}
    dry["hFacC"][[0, -1]] = 0.0                        # both polar rows land
    expect = _array_neighbours(dry["hFacC"], closes=True)
    assert len(expect) == 7650
    assert _edge_set(T.wet_graph(dry, connectivity="exch2")) == expect
    assert _edge_set(T.wet_graph(dry, connectivity="latlon")) == expect
    # regional 60N-90N, and the same through the data.exch2 default of a grid directory
    wet = np.ones((15, 20))
    cap = latlon_grid(np.arange(0, 41, 2.0), np.arange(60, 91, 2.0), wet)
    with pytest.raises(BuildError, match=r"cell 280 \(i=0, j=14.*collapses onto the north pole"):
        T.wet_graph(cap, connectivity="exch2")
    g = T.wet_graph(cap, connectivity="latlon")
    assert _edge_set(g) == _array_neighbours(wet) and len(_edge_set(g)) == 565
    gd = make_grid_dir(tmp_path, cap)
    write_text(os.path.join(gd, "data.exch2"), " &W2_EXCH2_PARM01\n &\n")
    src = [{"source_id": "s", "lon": 19.0, "lat": 81.0}]          # a cell center
    kw = dict(emission="spread", spread_type="gaussian", spread_scale="300km")
    with pytest.raises(BuildError, match="zero-length edge.*connectivity='latlon'"):
        build_targets(src, gd, **kw)
    t = build_targets(src, gd, connectivity="latlon", **kw)
    write_checked(tmp_path, t, cap, "cap.nc")


def rotated_block(nx, ny, dlon, dlat, wet, lon0=30.0, lat0=88.3):
    """A lat-lon block centred on (0, 0), rotated so its centre is at (lon0, lat0):
    one logically rectangular block whose XC and YC both vary with i and j."""
    grid = latlon_grid(dlon * (np.arange(nx + 1) - nx / 2.0),
                       dlat * (np.arange(ny + 1) - ny / 2.0), wet)
    th, ph = math.radians(lat0), math.radians(lon0)
    for xn, yn in (("XC", "YC"), ("XG", "YG")):
        lo, la = np.radians(grid[xn]), np.radians(grid[yn])
        x, y, z = np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)
        x, z = x * math.cos(th) - z * math.sin(th), x * math.sin(th) + z * math.cos(th)
        x, y = x * math.cos(ph) - y * math.sin(ph), x * math.sin(ph) + y * math.cos(ph)
        grid[xn], grid[yn] = np.degrees(np.arctan2(y, x)), np.degrees(np.arcsin(z))
    return grid


@pytest.mark.parametrize("dlon, dlat", [(1.0, 1.0), (2.0, 0.5)])
def test_rotated_block_is_exact_under_exch2_and_refused_under_latlon(dlon, dlat):
    """A block rotated over the North Pole is not a regular lat-lon grid: declared
    ``exch2`` the graph is the block's array neighbours; declared ``latlon`` is an
    error naming the field that varies."""
    nx, ny = 9, 8
    rng = np.random.default_rng(11)
    for wet in (np.ones((ny, nx)), (rng.random((ny, nx)) > 0.3) * 1.0):
        grid = rotated_block(nx, ny, dlon, dlat, wet)
        assert np.ptp(grid["YC"][0]) > 0.1 and grid["YC"].max() > 89.0      # spans the pole
        g = T.wet_graph(grid, connectivity="exch2")
        assert g.connectivity == "exch2" and not g.periodic
        assert _edge_set(g) == _array_neighbours(wet)
        with pytest.raises(BuildError, match="lat-lon block: XC varies from .* along column i"):
            T.wet_graph(grid, connectivity="latlon")


def test_latlon_declared_on_an_irregular_grid_is_an_error():
    """``latlon`` is checked, not trusted: a perturbed centre, two blocks side by side
    with a gap in longitude, and a spread build on such a grid all stop with an error
    that names the violation."""
    wet = np.ones((6, 8))
    grid = latlon_grid(10.0 + np.arange(9), 40.0 + np.arange(7), wet)
    assert T._latlon_problem(T._Geom(grid, R)) is None
    bent = {k: v.copy() for k, v in grid.items()}
    bent["YC"][3, 5] += 0.01
    with pytest.raises(BuildError, match="YC varies from 43.5 to 43.51 degrees along row j = 3"):
        T.wet_graph(bent, connectivity="latlon")
    east = latlon_grid(30.0 + np.arange(9), 40.0 + np.arange(7), wet)
    gap = {k: np.hstack([grid[k], east[k]]) for k in grid}
    with pytest.raises(BuildError) as e:
        build_targets([{"source_id": "s", "lon": 12.5, "lat": 42.5}], gap, emission="spread",
                      spread_type="gaussian", spread_scale="200km", connectivity="latlon")
    msg = str(e.value)
    assert "connectivity 'latlon' was declared" in msg and "connectivity='exch2'" in msg
    assert "column i = 7 ends at 18 degrees (2 XC - XG), but column i = 8 starts at 30" in msg
    # the same grid declared exch2: the two blocks are separate components
    g = T.wet_graph(gap, connectivity="exch2")
    assert _edge_set(g) == (_array_neighbours(np.hstack([wet, 0 * wet]))
                            | _array_neighbours(np.hstack([0 * wet, wet])))


def test_connectivity_is_declared_or_defaults_to_exch2_with_data_exch2(tmp_path):
    """No inference from geometry: without ``connectivity`` a spread build stops with
    an error explaining the two choices, unless the grid directory holds data.exch2,
    which selects ``exch2``. Pointwise sources need no graph and no declaration."""
    grid, src = channel()
    kw = dict(emission="spread", spread_type="gaussian", spread_scale=2 * DELTA)
    with pytest.raises(BuildError) as e:
        build_targets([src], grid, **kw)
    msg = str(e.value)
    assert "connectivity is not set and the grid was given as arrays" in msg
    for word in ("connectivity='latlon'", "--connectivity latlon", "connectivity='exch2'",
                 "--connectivity exch2", "data.exch2", "no default for lat-lon"):
        assert word in msg
    gd = make_grid_dir(tmp_path, grid)
    for call in (lambda: build_targets([src], gd, **kw), lambda: T.wet_graph(gd)):
        with pytest.raises(BuildError, match="has no data.exch2 file"):
            call()
    assert build_targets([src], gd).connectivity is None           # pointwise: no graph
    with pytest.raises(BuildError, match="'auto' is not one of latlon, exch2"):
        build_targets([src], gd, connectivity="auto", **kw)
    write_text(os.path.join(gd, "data.exch2"), " &W2_EXCH2_PARM01\n &\n")
    assert T.wet_graph(gd).connectivity == "exch2"
    t = build_targets([src], gd, **kw)
    assert t.connectivity == "exch2"
    declared = build_targets([src], gd, connectivity="latlon", **kw)
    assert declared.connectivity == "latlon"                      # a declaration wins
    np.testing.assert_array_equal(t.target_cell, declared.target_cell)
    np.testing.assert_array_equal(t.target_fraction, declared.target_fraction)
    write_checked(tmp_path, t, grid, "default_exch2.nc")


@needs_cs32
def test_cs32_directory_with_data_exch2_defaults_to_exch2(tmp_path):
    grid = T.read_grid(str(CS32))
    gd = make_grid_dir(tmp_path, grid)
    with pytest.raises(BuildError, match="connectivity is not set"):
        T.wet_graph(gd)
    write_text(os.path.join(gd, "data.exch2"), " &W2_EXCH2_PARM01\n &\n")
    g = T.wet_graph(gd)
    assert g.connectivity == "exch2" and len(_edge_set(g)) == 8438


@needs_cs32
def test_cs32_wet_graph():
    g = T.wet_graph(str(CS32), connectivity="exch2")
    nb = g.neighbours
    for k in range(len(nb)):
        for m in nb[k][nb[k] >= 0].tolist():
            assert k in nb[m].tolist()
    deg = np.bincount(g.degree(), minlength=5)
    assert deg[4] > 0 and deg[1:4].sum() > 0 and deg.size == 5
    a, b = g.edges()
    assert (_face(g.cells[a]) != _face(g.cells[b])).sum() > 200


@needs_cs32
def test_cs32_spread_sources_cross_faces(tmp_path):
    grid = T.read_grid(str(CS32))
    g = T.wet_graph(grid, connectivity="exch2")
    a, b = g.edges()
    cross = np.nonzero(_face(g.cells[a]) != _face(g.cells[b]))[0]
    lon, lat = grid["XC"].ravel(), grid["YC"].ravel()
    src = []
    for k, e in enumerate(cross[[0, len(cross) // 2, -1]].tolist()):
        c = int(g.cells[a[e]])
        src.append({"source_id": "edge{0}".format(k), "lon": float(lon[c]),
                    "lat": float(lat[c]), "spread_scale": "500km"})
    # The pole is the centre of the polar face: its nearest cell on another face is
    # 6062 km away along the water, so this source needs a cutoff (3X) beyond that.
    src.append({"source_id": "npole", "lon": 0.0, "lat": 88.0, "spread_scale": "2500km"})
    t = build_targets(src, str(CS32), emission="spread", spread_type="gaussian",
                      max_snap_distance="400km", connectivity="exch2")
    out = write_targets(str(tmp_path / "cs32.nc"), t)
    assert_clean(out, str(CS32))
    pos = {int(c): k for k, c in enumerate(g.cells.tolist())}
    for s in src:
        cells, f, r = rows(t, s["source_id"])
        assert len(set(_face(cells).tolist())) >= 2, s["source_id"]
        assert math.fsum(f) == pytest.approx(1.0, abs=1e-15)
        # contiguous: every target is reached from the snapped cell through targets
        nodes = {pos[c] for c in cells.tolist()}
        start = pos[int(t.source_snap_cell[t.source_id.index(s["source_id"])])]
        seen, todo = {start}, [start]
        while todo:
            v = todo.pop()
            for m in g.neighbours[v].tolist():
                if m in nodes and m not in seen:
                    seen.add(m)
                    todo.append(m)
        assert seen == nodes, s["source_id"]


# ---------------------------------------------------------------------------
# Scale


def test_scale_1000x1000_2000_spread_sources(tmp_path):
    """0.1-degree 1000 x 1000 grid, 2000 coastal sources, gaussian X ~ 3 cells."""
    lon_e = 0.1 * np.arange(1001)
    lat_e = 0.1 * np.arange(1001) - 50.0
    xc = 0.5 * (lon_e[:-1] + lon_e[1:])
    yc = 0.5 * (lat_e[:-1] + lat_e[1:])
    land = (np.sin(np.radians(7 * xc))[None, :] * np.cos(np.radians(5 * yc))[:, None]) > 0.35
    grid = latlon_grid(lon_e, lat_e, ~land)
    wet = ~land
    coast = wet & (np.roll(land, 1, 0) | np.roll(land, -1, 0) | np.roll(land, 1, 1)
                   | np.roll(land, -1, 1))
    jj, ii = np.nonzero(coast)
    rng = np.random.default_rng(20260930)
    pick = rng.choice(jj.size, 2000, replace=False)
    src = [{"source_id": "s{0:04d}".format(k), "lon": float(xc[ii[p]] + rng.uniform(-0.03, 0.03)),
            "lat": float(yc[jj[p]] + rng.uniform(-0.03, 0.03))} for k, p in enumerate(pick)]
    t0 = time.perf_counter()
    t = build_targets(src, grid, emission="spread", spread_type="gaussian",
                      spread_scale="33km", connectivity="latlon")
    elapsed = time.perf_counter() - t0
    print("\nscale test: 1000x1000 grid ({0} wet cells), 2000 spread sources, {1} targets: "
          "build_targets {2:.2f} s".format(int(wet.sum()), t.target_cell.size, elapsed))
    assert elapsed < 30.0
    # cutoff 3X = 99 km covers ~9 cells each way; coastal discs are partly land
    per_source = np.bincount(t.target_source, minlength=2000)
    assert len(t.source_id) == 2000 and per_source.min() > 1 and per_source.mean() > 30
    sums = np.bincount(t.target_source, weights=t.target_fraction)
    assert np.abs(sums - 1.0).max() < 1e-14
    t1 = time.perf_counter()
    gd = make_grid_dir(tmp_path, grid)
    out = write_targets(str(tmp_path / "scale.nc"), t)
    assert_clean(out, gd)
    print("scale test: write + grid files + checker {0:.2f} s".format(time.perf_counter() - t1))


# ---------------------------------------------------------------------------
# Round trip, writing into an existing file


def append_series(path, nt=3):
    """Append daily time series (flux only) to a tables-only file with netCDF4."""
    with netCDF4.Dataset(path, "a") as ds:
        ns = len(ds.dimensions["source"])
        ds.createDimension("time", None)
        ds.createDimension("nv", 2)
        tv = ds.createVariable("time", "f8", ("time",))
        tv.setncatts({"units": "days since 2000-01-01 00:00:00", "calendar": "standard",
                      "axis": "T", "standard_name": "time", "bounds": "time_bnds"})
        tb = ds.createVariable("time_bnds", "f8", ("time", "nv"))
        fl = ds.createVariable("runoff_flux", "f4", ("time", "source"),
                               chunksizes=(1, ns), zlib=True, complevel=2, shuffle=True)
        fl.units = "m3 s-1"
        tv[:] = np.arange(nt) + 0.5
        tb[:] = np.stack([np.arange(nt), np.arange(nt) + 1.0], 1)
        fl[:] = 100.0 + np.arange(nt * ns, dtype="f4").reshape(nt, ns)
        ds.mitgcm_time_sampling = "fixed"
        ds.mitgcm_time_period = 86400.0
    return path


def test_round_trip_and_write_into(tmp_path):
    grid = coast_grid()
    gd = make_grid_dir(tmp_path, grid)
    src = [{"source_id": "a", "lon": 0.8, "lat": 0.0, "alt_names": "Alpha"},
           {"source_id": "b", "lon": 1.3, "lat": 0.4}]
    spread = build_targets(src, gd, emission="spread", spread_type="exponential",
                           spread_scale="10km", connectivity="latlon")
    out = write_targets(str(tmp_path / "runoff.nc"), spread, history="test build")
    assert_clean(out, gd)
    append_series(out)
    assert_clean(out, gd, tables_only=False)
    with netCDF4.Dataset(out) as ds:
        flux = ds["runoff_flux"][:].copy()
        assert ds.history.endswith(": test build")
    # replace the tables: pointwise now; the time series are kept
    point = build_targets(src, gd)
    new = write_targets(str(tmp_path / "runoff_point.nc"), point, into=out)
    assert_clean(new, gd, tables_only=False)
    with netCDF4.Dataset(new) as ds:
        np.testing.assert_array_equal(ds["runoff_flux"][:], flux)
        assert ds["runoff_flux"].chunking() == [1, 2]
        assert ds["runoff_flux"].filters()["zlib"]
        assert ds.dimensions["time"].isunlimited()
        assert ds["target_fraction"][:].tolist() == [1.0, 1.0]
        assert list(ds["source_emission"][:]) == ["pointwise", "pointwise"]
        assert list(ds["alias_name"][:]) == ["Alpha"]
        assert len(ds.history.splitlines()) == 2
    # in place
    write_targets(new, spread, into=new)
    assert_clean(new, gd, tables_only=False)
    with netCDF4.Dataset(new) as ds:
        assert ds.dimensions["target"].size == spread.target_cell.size
        np.testing.assert_array_equal(ds["runoff_flux"][:], flux)
    # a different source list is refused and the file is left alone
    other = build_targets(src[::-1], gd)
    before = open(new, "rb").read()
    with pytest.raises(BuildError, match="source_id list differs"):
        write_targets(new, other, into=new)
    assert open(new, "rb").read() == before
    assert not [p for p in os.listdir(tmp_path) if p.startswith(".targets-")]


def test_schema_doc_section_13_example(tmp_path, monkeypatch):
    """The CSV and Python blocks of schema section 13 run as documented."""
    import re
    doc = (ROOT / "docs" / "runoff_schema.md").read_text(encoding="utf-8")
    section = doc.split("## 13. Building the target table", 1)[1]
    csv_text = re.search(r"```text\n(.*?)```", section, re.S).group(1)
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    # 0.1-degree grid over 60W-40W, 5S-75N, all wet: covers both example sources
    grid = latlon_grid(-60 + 0.1 * np.arange(201), -5 + 0.1 * np.arange(801),
                       np.ones((800, 200)))
    make_grid_dir(tmp_path, grid, "run")
    write_text(tmp_path / "sources.csv", csv_text)
    monkeypatch.chdir(tmp_path)
    ns = {"__name__": "__doc13__"}
    exec(compile(code, "docs/runoff_schema.md#13", "exec"), ns)
    t = ns["tables"]
    assert t.source_emission == ["spread", "pointwise"]          # jakobshavn, amazon
    assert t.source_spread_type == ["gaussian", "none"]
    assert t.source_spread_scale[0] == 10000.0
    assert (t.target_source == 1).sum() == 1 and (t.target_source == 0).sum() > 1
    assert_clean(str(tmp_path / "targets.nc"), str(tmp_path / "run"))


# ---------------------------------------------------------------------------
# Command line and package exports


def _env():
    return dict(os.environ, PYTHONPATH=str(ROOT / "MITgcm" / "utils" / "python" / "MITgcmutils"))


def test_cli(tmp_path):
    grid = coast_grid()
    gd = make_grid_dir(tmp_path, grid)
    csv_path = write_text(tmp_path / "s.csv", "source_id,lon,lat\nr1,0.8,0.0\nr2,1.2,0.3\n")
    out = str(tmp_path / "out.nc")
    r = subprocess.run([sys.executable, "-W", "error::RuntimeWarning", "-m",
                        "MITgcmutils.runoff.targets", csv_path, "--grid-dir", gd, "-o", out,
                        "--emission", "spread", "--spread-type", "gaussian",
                        "--spread-scale", "8km", "--grid-name", "coast",
                        "--connectivity", "latlon"],
                       env=_env(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 error(s), 0 warning(s)" in r.stdout and "S10" in r.stdout
    assert "connectivity latlon" in r.stdout
    with netCDF4.Dataset(out) as ds:
        assert "-m MITgcmutils.runoff.targets" in ds.history and "--spread-scale 8km" in ds.history
        assert ds.mitgcm_grid_name == "coast"
    assert_clean(out, gd)
    assert T.main([csv_path, "--grid-dir", gd, "-o", out, "--max-snap-distance", "1m"]) == 1
    assert T.main([csv_path, "--grid-dir", gd]) == 2                     # no -o
    # spread sources without --connectivity (and no data.exch2 in the grid directory)
    assert T.main([csv_path, "--grid-dir", gd, "-o", out, "--emission", "spread",
                   "--spread-type", "linear", "--spread-scale", "8km"]) == 1
    assert T.main([csv_path, "--grid-dir", gd, "-o", out, "--connectivity", "auto"]) == 2
    assert T.main([csv_path, "--grid-dir", str(tmp_path / "nogrid"), "-o", out]) == 2


def test_package_exports_are_lazy():
    code = "\n".join([
        "import sys",
        "import MITgcmutils.runoff as R",
        "assert 'MITgcmutils.runoff.targets' not in sys.modules",
        "from MITgcmutils.runoff import build_targets, write_targets",
        "from MITgcmutils.runoff.targets import build_targets as b, write_targets as w",
        "assert build_targets is b and write_targets is w",
        "assert {'build_targets', 'write_targets'} <= set(R.__all__)",
    ])
    r = subprocess.run([sys.executable, "-W", "error::RuntimeWarning", "-c", code],
                       env=_env(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
