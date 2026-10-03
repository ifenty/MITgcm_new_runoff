"""Tests of the dense <-> sparse runoff converter (RUNOFF-002).

Oracles:

* round trip: dense -> sparse -> dense gives back the dense records of the six
  lab_sea runoff cases (float32, exactly) and of cs32 (float64: runoff to one
  unit in the last place and exactly at float32, temperature exactly);
* every converted file passes the full integrity checker with no error and no
  warning, with the grid checks R01-R03;
* synthetic lat-lon and exch2-shaped grids with fractions, fluxes and
  temperatures computed in the test from the inputs, and a hand-built file
  with two sources feeding one cell (volumes add, temperature is the
  flux-weighted mean);
* the time axis of each exf timing mode against values worked out by hand
  (day counts of calendar months and years), not by the converter's helpers;
* the runoff field at every forcing time of the six lab_sea oracle runs: the
  sparse file, read by the schema's rules (:class:`SparseReader`, written
  here), against the field pkg/exf applies from the dense file, as computed
  by ``lab_sea_runoff_timing_check.Case``, which the direct timing check
  compares with the model's own monitor output.

The cs32 tests read the cubed-sphere grid output of a model run and are
skipped when no run directory exists.
"""

import datetime as dt
import glob
import importlib.util
import re

import netCDF4
import numpy as np
import pytest

import lab_sea_runoff_timing_check as timing
from conftest import ROOT, write_mds
from MITgcmutils.runoff import check_files, convert, dense_to_sparse, sparse_to_dense
from MITgcmutils.runoff.convert import ConvertError, time_axis

VERIF = ROOT / "MITgcm" / "verification"
LAB = VERIF / "lab_sea"
CS32 = VERIF / "global_ocean.cs32x15"
GEN = LAB / "input.rnof_const" / "gen_sparse.py"

_spec = importlib.util.spec_from_file_location("gen_sparse", str(GEN))
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

LAB_CASES = ["const", "daily", "month", "month1", "clim", "yearly"]
#: Dense records of each lab_sea case (file sizes / (20*16*4 bytes)).
LAB_NREC = {"const": 1, "daily": 40, "month": 12, "month1": 6, "clim": 12, "yearly": 365}
#: The seven lab_sea source cells, cell = i + 20*j (runoff_sources.txt).
LAB_CELLS = [52, 147, 167, 233, 288, 289, 290]
#: Day number of the first day of each month in a 365-day year, then 365.
MONTH_STARTS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]

cs32_grid = gen.cs32_grid_dir()
needs_cs32 = pytest.mark.skipif(cs32_grid is None,
                                reason="no cs32 grid output (run the cs32 oracle first)")


def read(path):
    """Variables, global attributes, ids and time attributes of a sparse file."""
    with netCDF4.Dataset(str(path)) as ds:
        ds.set_auto_mask(False)
        out = {k: np.asarray(v[:]) for k, v in ds.variables.items() if k != "source_id"}
        chars = np.asarray(ds.variables["source_id"][:])
        out["ids"] = [row.tobytes().rstrip(b"\x00").decode("ascii") for row in chars]
        out["attrs"] = {k: ds.getncattr(k) for k in ds.ncattrs()}
        out["units"] = ds.variables["time"].units
        out["calendar"] = ds.variables["time"].calendar
        out["dtypes"] = {k: v.dtype for k, v in ds.variables.items()}
    return out


def assert_clean(report):
    """No error and no warning; show the findings otherwise."""
    bad = report.errors + report.warnings
    assert not bad, "\n".join("{0}: {1}".format(f.rule, f.message) for f in bad)


def dense_file(case, path):
    """The dense file a lab_sea sparse file was converted from."""
    name = gen.LAB_CASES[case]["dense"]
    if case == "yearly":
        name += "_" + re.search(r"_(\d{4})\.nc$", str(path)).group(1)
    return LAB / ("input.rnof_" + case) / name


@pytest.fixture
def lab_grid_dir(tmp_path):
    """The lab_sea grid of gen_sparse.py as MITgcm grid output (hFacC 3D)."""
    d = tmp_path / "labgrid"
    d.mkdir()
    rac, hfac, xc, yc = gen.lab_sea_grid()
    write_mds(str(d / "hFacC"), np.stack([hfac, hfac]), tiles=(2, 2))
    write_mds(str(d / "RAC"), rac)
    write_mds(str(d / "XC"), xc)
    write_mds(str(d / "YC"), yc)
    return str(d)


@pytest.fixture(scope="module")
def cs32_file(tmp_path_factory):
    return gen.cs32(out_dir=str(tmp_path_factory.mktemp("cs32")))[0]


# ---------------------------------------------------------------------------
# The real cases: round trip, checker, regeneration


@pytest.mark.parametrize("case", LAB_CASES)
def test_lab_sea_round_trip_is_exact_in_float32(case, tmp_path):
    paths = gen.lab_sea(case, out_dir=str(tmp_path))
    # const: grouped and per-cell files; yearly: two years; else one file.
    assert len(paths) == (2 if case in ("const", "yearly") else 1)
    for path in paths:
        orig = np.fromfile(str(dense_file(case, path)), ">f4").reshape(-1, 16, 20)
        assert orig.shape[0] == LAB_NREC[case]
        back = sparse_to_dense(path)
        assert back.dtype == np.dtype(">f4")
        assert back.shape == orig.shape
        for r in range(orig.shape[0]):
            assert np.array_equal(back[r], orig[r]), (path, r)
        assert sorted(np.unique(read(path)["target_cell"])) == LAB_CELLS


@pytest.mark.parametrize("case", LAB_CASES)
def test_lab_sea_files_pass_the_checker(case, tmp_path, lab_grid_dir):
    paths = gen.lab_sea(case, out_dir=str(tmp_path))
    sets = [paths] if case == "yearly" else [[p] for p in paths]
    for files in sets:
        report = check_files(files, grid_dir=lab_grid_dir)
        assert_clean(report)
        assert report.stats.get("tables_only") is None


def test_lab_sea_grouping():
    """const keeps the groups of runoff_sources.txt; the timed cases cannot."""
    const = read(LAB / "input.rnof_const" / "runoff_sparse.nc")
    assert const["ids"] == ["newfound", "labrador", "greenland", "baffin"]
    assert list(const["target_cell"]) == LAB_CELLS
    assert list(const["target_source"]) == [0, 1, 1, 2, 3, 3, 3]
    # Shares of the one record: dense * rA, computed here from the inputs.
    rac = gen.lab_sea_grid()[0].ravel()
    dense = np.fromfile(str(LAB / "input.rnof_const" / "runoff_const.bin"),
                        ">f4").astype("f8")
    vol = dense[LAB_CELLS] * rac[LAB_CELLS]
    want = np.array([1.0, vol[1] / vol[1:3].sum(), vol[2] / vol[1:3].sum(), 1.0,
                     vol[4] / vol[4:].sum(), vol[5] / vol[4:].sum(),
                     vol[6] / vol[4:].sum()])
    assert np.abs(const["target_fraction"] - want).max() < 1e-15
    assert np.abs(const["runoff_flux"][0]
                  - [vol[0], vol[1:3].sum(), vol[3], vol[4:].sum()]).max() \
        < 1e-12 * vol.max()
    cells = read(LAB / "input.rnof_const" / "runoff_sparse_cells.nc")
    assert cells["ids"] == ["cell_{0:03d}".format(c) for c in LAB_CELLS]
    daily = read(LAB / "input.rnof_daily" / "runoff_sparse.nc")
    assert daily["ids"] == ["newfound", "labrador_147", "labrador_167", "greenland",
                            "baffin_288", "baffin_289", "baffin_290"]
    assert np.all(daily["target_fraction"] == 1.0)
    # Without split_varying the varying shares are refused, naming the source.
    rac, hfac, _, _ = gen.lab_sea_grid()
    with pytest.raises(ConvertError, match="'(labrador|baffin)'.*shares"):
        dense_to_sparse(str(LAB / "input.rnof_daily" / "runoff_daily.bin"), "unused.nc",
                        rac=rac, hfac=hfac, period=86400.0, startdate1=19790101,
                        sources=str(LAB / "input.rnof_daily" / "runoff_sources.txt"))


@pytest.mark.parametrize("case", LAB_CASES)
def test_committed_lab_sea_files_are_regenerated_identically(case, tmp_path):
    for path in gen.lab_sea(case, out_dir=str(tmp_path)):
        name = path.rsplit("/", 1)[1]
        new, old = read(path), read(LAB / ("input.rnof_" + case) / name)
        assert sorted(new) == sorted(old)
        for key in new:
            if key in ("attrs", "dtypes"):
                assert new[key].keys() == old[key].keys()
                for k in new[key]:
                    assert np.all(new[key][k] == old[key][k]), (key, k)
            else:
                assert np.array_equal(new[key], old[key]), key


def test_gen_sparse_settings_match_data_exf():
    """gen_sparse.py uses the runoff timing of each case's data.exf."""
    names = {"period": "runoffperiod", "startdate1": "runoffstartdate1",
             "startdate2": "runoffstartdate2", "repeat_cycle": "runoffRepCycle"}
    for case, kw in gen.LAB_CASES.items():
        text = (LAB / ("input.rnof_" + case) / "data.exf").read_text()
        found = {}
        for key, name in names.items():
            m = re.search(r"^\s*{0}\s*=\s*([-0-9.eE+]+)".format(name), text, re.M)
            if m:
                found[key] = float(m.group(1))
        assert found, case
        for key, value in found.items():
            assert float(kw[key]) == value, (case, key)
        assert set(kw) - {"dense", "years", "clim_year"} == set(found), case
        yearly = re.search(r"^\s*useExfYearlyFields\s*=\s*\.TRUE\.", text, re.M)
        assert bool(yearly) == ("years" in kw)
        assert re.search(r"^\s*exf_iprec\s*=\s*32", text, re.M)
    text = (CS32 / "input.icedyn" / "data.exf").read_text()
    for name, value in (("runoffStartTime", 1296000.0), ("runoffperiod", 2592000.0),
                        ("repeatPeriod", 31104000.0), ("exf_iprec", 64.0)):
        m = re.search(r"^\s*{0}\s*=\s*([-0-9.eE+]+)".format(name), text, re.M)
        assert float(m.group(1)) == value
    assert "runoffRepCycle" not in text       # so the cycle is repeatPeriod
    # No calendar package in cs32: its times are seconds of model time.
    assert "-cal" in (CS32 / "code" / "packages.conf").read_text().split()


def test_lab_sea_grid_matches_model_output():
    """gen_sparse.py's analytic grid equals the grid a lab_sea run wrote (mnc)."""
    tiles = sorted(glob.glob(str(LAB / "output_esx_input" / "mnc_test_*" / "grid.t*.nc")))
    if not tiles:
        pytest.skip("no lab_sea run output (run the lab_sea oracle first)")
    rac, hfac, xc, yc = gen.lab_sea_grid()
    seen = np.zeros(rac.shape, dtype=bool)
    for tile in tiles:
        with netCDF4.Dataset(tile) as ds:
            x, y = np.asarray(ds.variables["xC"][:]), np.asarray(ds.variables["yC"][:])
            i = np.rint((x - 281.0) / 2.0).astype(int)
            j = np.rint((y - 47.0) / 2.0).astype(int)
            assert np.abs(np.asarray(ds.variables["rAc"][:]) / rac[j, i] - 1.0).max() < 1e-13
            assert np.array_equal(np.asarray(ds.variables["hFacC"][0]) > 0, hfac[j, i] > 0)
            assert np.abs(x - xc[j, i]).max() < 1e-10 and np.abs(y - yc[j, i]).max() < 1e-10
            seen[j, i] = True
    assert seen.all()


@needs_cs32
def test_cs32_round_trip(cs32_file):
    orig = np.fromfile(str(CS32 / "input.icedyn" / "core_rnof_1_cs32.bin"),
                       ">f8").reshape(12, 32, 192)
    back = sparse_to_dense(cs32_file)
    assert back.dtype == np.dtype(">f8") and back.shape == orig.shape
    # Exact at float32, and within one unit in the last place at float64.
    assert np.array_equal(back.astype(">f4"), orig.astype(">f4"))
    native, ref = back.astype("f8"), orig.astype("f8")
    assert np.all(np.abs(native - ref) <= np.spacing(ref))
    assert np.array_equal(native == 0.0, ref == 0.0)
    # Where it is not exact, no float64 flux gives the dense value back.
    rac = np.broadcast_to(convert._grid(cs32_grid, None, None, None, None)[0], ref.shape)
    off = native != ref
    assert 0 < off.sum() < 0.2 * (ref != 0.0).sum()
    flux = ref[off] * rac[off]
    for direction in (-np.inf, np.inf):
        f = flux.copy()
        for _ in range(3):
            f = np.nextafter(f, direction)
            assert not np.any(f / rac[off] == ref[off])
    # Total volume flux of each record, from the dense file and the grid.
    data = read(cs32_file)
    total = (ref * rac).reshape(12, -1).sum(axis=1)
    assert np.abs(data["runoff_flux"].sum(axis=1) / total - 1.0).max() < 1e-12
    assert data["dtypes"]["runoff_flux"] == np.float64
    assert data["attrs"]["mitgcm_grid_nx"] == 192 and data["attrs"]["mitgcm_grid_ny"] == 32
    assert len(data["ids"]) == 1189 and np.all(data["target_fraction"] == 1.0)


@needs_cs32
def test_cs32_temperature_round_trip_is_exact(cs32_file):
    orig = np.fromfile(str(CS32 / "input.seaice" / "runoff_temperature.bin"),
                       ">f8").reshape(12, 32, 192)
    back = sparse_to_dense(cs32_file, variable="runoff_temperature")
    for r in range(12):
        assert np.array_equal(back[r], orig[r]), r
    assert np.all(read(cs32_file)["runoff_temperature"] == 30.0)


@needs_cs32
def test_cs32_file_passes_the_checker_and_matches_the_committed_file(cs32_file):
    assert_clean(check_files(cs32_file, grid_dir=cs32_grid))
    new, old = read(cs32_file), read(CS32 / "input.rnof_sparse" / "runoff_sparse.nc")
    for key in new:
        if key not in ("attrs", "dtypes"):
            assert np.array_equal(new[key], old[key]), key


@needs_cs32
def test_cs32_time_axis(cs32_file):
    """runoffStartTime 1296000 s, period 2592000 s, cycle 31104000 s, no pkg/cal."""
    d = read(cs32_file)
    assert d["units"] == "days since 0001-01-01 00:00:00" and d["calendar"] == "360_day"
    assert np.array_equal(d["time"], 15.0 + 30.0 * np.arange(12))
    assert np.array_equal(d["time_bnds"][:, 0], 30.0 * np.arange(12))
    assert np.array_equal(d["time_bnds"][:, 1], 30.0 * np.arange(1, 13))
    assert d["attrs"]["mitgcm_time_sampling"] == "fixed"
    assert d["attrs"]["mitgcm_time_period"] == 2592000.0
    assert d["attrs"]["mitgcm_time_repeat"] == "annual"


# ---------------------------------------------------------------------------
# Time axis of each lab_sea case, against hand-computed values


def test_time_constant(tmp_path):
    d = read(gen.lab_sea("const", out_dir=str(tmp_path))[0])
    assert np.array_equal(d["time"], [0.0]) and "time_bnds" not in d
    assert d["units"] == "days since 0001-01-01 00:00:00" and d["calendar"] == "gregorian"
    assert d["attrs"]["mitgcm_time_sampling"] == "constant"
    assert "mitgcm_time_period" not in d["attrs"]
    assert d["attrs"]["mitgcm_time_repeat"] == "none"


def test_time_daily(tmp_path):
    """Record k at 1 January 1979 00:00 + k days; bounds centred on it."""
    d = read(gen.lab_sea("daily", out_dir=str(tmp_path))[0])
    assert d["units"] == "days since 1979-01-01 00:00:00"
    assert np.array_equal(d["time"], np.arange(40.0))
    assert np.array_equal(d["time_bnds"][:, 0], np.arange(40.0) - 0.5)
    assert np.array_equal(d["time_bnds"][:, 1], np.arange(40.0) + 0.5)
    assert d["attrs"]["mitgcm_time_sampling"] == "fixed"
    assert d["attrs"]["mitgcm_time_period"] == 86400.0
    assert d["attrs"]["mitgcm_time_repeat"] == "none"


def test_time_monthly_climatology(tmp_path):
    """Period -12: the twelve months of the nominal year 1979, mid-month times."""
    d = read(gen.lab_sea("month", out_dir=str(tmp_path))[0])
    assert d["units"] == "days since 1979-01-01 00:00:00"
    assert np.array_equal(d["time_bnds"][:, 0], MONTH_STARTS[:-1])
    assert np.array_equal(d["time_bnds"][:, 1], MONTH_STARTS[1:])
    assert np.array_equal(d["time"], [15.5, 45.0, 74.5, 105.0, 135.5, 166.0, 196.5,
                                      227.5, 258.0, 288.5, 319.0, 349.5])
    assert d["attrs"]["mitgcm_time_sampling"] == "monthly"
    assert "mitgcm_time_period" not in d["attrs"]
    assert d["attrs"]["mitgcm_time_repeat"] == "annual"


def test_time_calendar_months(tmp_path):
    """Period -1 from 1978-12-01: December 1978 to May 1979, not repeated."""
    d = read(gen.lab_sea("month1", out_dir=str(tmp_path))[0])
    assert d["units"] == "days since 1978-01-01 00:00:00"
    edges = [334.0, 365.0, 396.0, 424.0, 455.0, 485.0, 516.0]   # 1 Dec 1978 .. 1 Jun 1979
    assert np.array_equal(d["time_bnds"][:, 0], edges[:-1])
    assert np.array_equal(d["time_bnds"][:, 1], edges[1:])
    assert np.array_equal(d["time"], [349.5, 380.5, 410.0, 439.5, 470.0, 500.5])
    assert d["attrs"]["mitgcm_time_sampling"] == "monthly"
    assert d["attrs"]["mitgcm_time_repeat"] == "none"


def test_time_fixed_period_with_repeat_cycle(tmp_path):
    """clim: record 1 at 16 January 1978 12:00, period 365/12 days, cycle 365 days."""
    d = read(gen.lab_sea("clim", out_dir=str(tmp_path))[0])
    assert d["units"] == "days since 1978-01-01 00:00:00"
    step = 2628000.0 / 86400.0                    # 30.41666... days
    assert np.abs(d["time"] - (15.5 + step * np.arange(12))).max() < 1e-9
    # Bounds are centred, so the first starts 15.5 - 15.2083 = 0.2917 days in:
    # 1 January 1978 07:00. The last ends 365 days later.
    assert abs(d["time_bnds"][0, 0] - 7.0 / 24.0) < 1e-9
    assert abs(d["time_bnds"][-1, 1] - (365.0 + 7.0 / 24.0)) < 1e-9
    assert np.abs(d["time_bnds"][:, 1] - d["time_bnds"][:, 0] - step).max() < 1e-9
    assert np.array_equal(d["time_bnds"][1:, 0], d["time_bnds"][:-1, 1])
    assert d["attrs"]["mitgcm_time_sampling"] == "fixed"
    assert d["attrs"]["mitgcm_time_period"] == 2628000.0
    assert d["attrs"]["mitgcm_time_repeat"] == "annual"


def test_time_yearly_files(tmp_path):
    """Daily records from 1 January 00:00 in runoff_sparse_1978.nc and _1979.nc."""
    paths = gen.lab_sea("yearly", out_dir=str(tmp_path))
    assert [p.rsplit("/", 1)[1] for p in paths] == ["runoff_sparse_1978.nc",
                                                    "runoff_sparse_1979.nc"]
    for path, first in zip(paths, (0.0, 365.0)):
        d = read(path)
        assert d["units"] == "days since 1978-01-01 00:00:00"
        assert np.array_equal(d["time"], first + np.arange(365.0))
        assert np.array_equal(d["time_bnds"][:, 0], first + np.arange(365.0))
        assert np.array_equal(d["time_bnds"][:, 1], first + np.arange(1.0, 366.0))
        assert d["attrs"]["mitgcm_time_sampling"] == "fixed"
        assert d["attrs"]["mitgcm_time_period"] == 86400.0
        assert d["attrs"]["mitgcm_time_repeat"] == "none"
    a, b = read(paths[0]), read(paths[1])
    for key in ("ids", "target_source", "target_cell", "target_fraction"):
        assert np.array_equal(a[key], b[key])


# ---------------------------------------------------------------------------
# The sparse files give the field exf applies, at every forcing time


def _mid_month(year, month):
    start = dt.datetime(year, month, 1)
    end = dt.datetime(year + month // 12, month % 12 + 1, 1)
    return start + (end - start) / 2


class SparseReader:
    """Runoff (m/s) of sparse files at a date, read by the rules of the schema.

    Linear interpolation between the ``time`` values (section 3.1). A
    ``monthly`` file with ``annual`` repeat has record ``m`` at the middle of
    month ``m`` of every model year; a ``fixed`` file with ``annual`` repeat
    repeats with the span of its bounds (section 7); yearly files form one
    series. ``shift`` moves every record by that many places, to show that
    the comparison notices a record chosen wrongly.

    For the monthly climatology the record times come from the calendar, not
    from the file's ``time`` values, so this reader does not see an error in
    them; ``test_time_monthly_climatology`` checks those values.
    """

    def __init__(self, paths, shift=0):
        parts = [read(p) for p in paths]
        d = parts[0]
        assert all(p["units"] == d["units"] for p in parts)
        self.ref = dt.datetime.strptime(d["units"], "days since %Y-%m-%d %H:%M:%S")
        self.sec = np.concatenate([p["time"] for p in parts]) * 86400.0
        self.flux = np.roll(np.concatenate([p["runoff_flux"] for p in parts]), shift, axis=0)
        self.sampling = d["attrs"]["mitgcm_time_sampling"]
        self.repeat = d["attrs"]["mitgcm_time_repeat"]
        if "time_bnds" in d:
            self.span = (parts[-1]["time_bnds"][-1, 1] - d["time_bnds"][0, 0]) * 86400.0
        self.src, self.cell = d["target_source"], d["target_cell"]
        self.scale = d["target_fraction"] / d["target_cell_area"]
        self.ncell = d["attrs"]["mitgcm_grid_nx"] * d["attrs"]["mitgcm_grid_ny"]

    def source_flux(self, date):
        n = self.sec.size
        if self.sampling == "constant":
            return self.flux[0]
        if self.sampling == "monthly" and self.repeat == "annual":
            y, m = date.year, date.month
            if date < _mid_month(y, m):
                y, m = (y, m - 1) if m > 1 else (y - 1, 12)
            y1, m1 = (y, m + 1) if m < 12 else (y + 1, 1)
            t0, t1 = _mid_month(y, m), _mid_month(y1, m1)
            w = (date - t0) / (t1 - t0)
            return (1.0 - w) * self.flux[m - 1] + w * self.flux[m1 - 1]
        x, sec = (date - self.ref).total_seconds(), self.sec
        if self.repeat == "annual":
            x = sec[0] + (x - sec[0]) % self.span
            sec = np.append(sec, sec[0] + self.span)
        k = int(np.searchsorted(sec, x, side="right")) - 1
        assert 0 <= k < n, "date outside the records"
        if x == sec[k]:
            return self.flux[k]
        assert k + 1 < sec.size, "date after the last record"
        w = (x - sec[k]) / (sec[k + 1] - sec[k])
        return (1.0 - w) * self.flux[k] + w * self.flux[(k + 1) % n]

    def dense(self, date):
        out = np.zeros(self.ncell)
        np.add.at(out, self.cell, self.source_flux(date)[self.src] * self.scale)
        return out


@pytest.mark.parametrize("case", LAB_CASES)
def test_sparse_file_gives_the_exf_field_at_every_forcing_time(case, tmp_path):
    """Every step of the lab_sea oracle run: sparse read = dense exf field."""
    paths = gen.lab_sea(case, out_dir=str(tmp_path))
    exf = timing.Case(str(LAB / ("input.rnof_" + case)))
    text = (LAB / ("input.rnof_" + case) / "data").read_text()
    start = float(timing.namelist_value(text, "startTime"))
    end = float(timing.namelist_value(text, "endTime"))
    step = float(timing.namelist_value(text, "deltaTClock"))
    assert step == 3600.0
    # Forcing is evaluated at the start of each step: startTime, ..., endTime - step.
    dates = [exf.base + dt.timedelta(seconds=start + step * n)
             for n in range(int(round((end - start) / step)))]
    assert len(dates) == {"const": 48, "daily": 768, "month": 1464, "month1": 1464,
                          "clim": 1200, "yearly": 624}[case]
    files = [[p] for p in paths] if case == "const" else [paths]
    readers = [SparseReader(f) for f in files]
    wrong = SparseReader(files[0], shift=1)
    peak = max(np.abs(exf.field(d)).max() for d in dates[::24])
    worst = shifted = 0.0
    for date in dates:
        want = exf.field(date).ravel()
        for reader in readers:
            worst = max(worst, np.abs(reader.dense(date) - want).max())
        shifted = max(shifted, np.abs(wrong.dense(date) - want).max())
    assert worst <= 1e-12 * peak
    if case != "const":
        # The check has power: records moved by one place change the field.
        assert shifted > 0.05 * peak
        first, last = exf.field(dates[0]), exf.field(dates[-1])
        assert np.abs(first - last).max() > 0.05 * peak


# ---------------------------------------------------------------------------
# time_axis: other calendars, offsets and refusals, by hand


def test_time_axis_month_lengths_by_calendar():
    # February 1980: 29 days (gregorian), 28 (noleap), 30 (360_day).
    for cal, start, end in (("gregorian", 31.0, 60.0), ("noLeapYear", 31.0, 59.0),
                            ("model", 30.0, 60.0)):
        ax = time_axis(-1, 1, startdate1=19800215, calendar=cal)
        assert ax["bounds"].tolist() == [[start, end]]
        assert ax["time"].tolist() == [0.5 * (start + end)]
        assert ax["units"] == "days since 1980-01-01 00:00:00"
    assert time_axis(-1, 1, startdate1=19800215, calendar="noLeapYear")["calendar"] == "noleap"
    assert time_axis(-1, 1, startdate1=19800215, calendar="model")["calendar"] == "360_day"
    # A leap nominal year for the climatology: February is 31..60.
    ax = time_axis(-12, 12, calendar="standard", clim_year=1980)
    assert ax["bounds"][1].tolist() == [31.0, 60.0] and ax["bounds"][-1, 1] == 366.0
    assert ax["repeat"] == "annual" and ax["sampling"] == "monthly"
    # Yearly files of monthly records: the twelve months of the file's year.
    ax = time_axis(-1, 12, year=1979, ref_year=1978, calendar="gregorian")
    assert ax["bounds"][:, 0].tolist() == [365.0 + m for m in MONTH_STARTS[:-1]]
    assert ax["nrec"] == 12 and ax["repeat"] == "none"


def test_time_axis_yearly_offset_and_leap_year():
    # Records at 12:00: offset 43200 s. In the 1979 file, units since 1978.
    ax = time_axis(86400.0, 365, startdate1=19780101, startdate2=120000, year=1979,
                   calendar="gregorian")
    assert np.array_equal(ax["time"], 365.5 + np.arange(365.0))
    assert np.array_equal(ax["bounds"][:, 0], 365.0 + np.arange(365.0))
    assert np.array_equal(ax["bounds"][:, 1], 366.0 + np.arange(365.0))
    # 1980 has 366 days on the gregorian calendar and 365 on noleap.
    assert time_axis(86400.0, 366, startdate1=19800101, year=1980,
                     calendar="gregorian")["nrec"] == 366
    assert time_axis(86400.0, 366, startdate1=19800101, year=1980,
                     calendar="noleap")["nrec"] == 365
    with pytest.raises(ConvertError, match="needs 366 records"):
        time_axis(86400.0, 365, startdate1=19800101, year=1980, calendar="gregorian")


def test_time_axis_without_calendar_dates():
    """cs32-style: seconds of model time, record 1 at start_time."""
    ax = time_axis(2592000.0, 12, start_time=1296000.0, repeat_cycle=31104000.0,
                   calendar="360_day")
    assert np.array_equal(ax["time"], 15.0 + 30.0 * np.arange(12))
    assert ax["bounds"][0].tolist() == [0.0, 30.0] and ax["bounds"][-1, 1] == 360.0
    assert ax["units"] == "days since 0001-01-01 00:00:00" and ax["repeat"] == "annual"
    # More records than the cycle holds: exf reads only cycle / period of them.
    assert time_axis(2592000.0, 14, start_time=1296000.0, repeat_cycle=31104000.0,
                     calendar="360_day")["nrec"] == 12
    # Hourly records, no repeat: record k at 1800 s + k hours.
    ax = time_axis(3600.0, 3, start_time=1800.0, calendar="noleap")
    assert np.allclose(ax["time"] * 24.0, [0.5, 1.5, 2.5], rtol=0, atol=1e-12)
    assert np.allclose(ax["bounds"] * 24.0, [[0, 1], [1, 2], [2, 3]], rtol=0, atol=1e-12)
    assert ax["repeat"] == "none" and ax["period"] == 3600.0


def test_time_axis_refusals():
    # A 360-day cycle is one year only on the 360_day calendar (rule M05).
    with pytest.raises(ConvertError, match="not one year.*M05"):
        time_axis(2592000.0, 12, start_time=1296000.0, repeat_cycle=31104000.0,
                  calendar="noleap")
    # exf's lab_sea default repeatPeriod, 366 days, on a 365-day year.
    with pytest.raises(ConvertError, match="not one year"):
        time_axis(86400.0, 366, startdate1=19790101, repeat_cycle=31622400.0,
                  calendar="gregorian")
    with pytest.raises(ConvertError, match="whole number of periods"):
        time_axis(86400.0, 10, start_time=0.0, repeat_cycle=100000.0, calendar="noleap")
    # Weekly records do not fill a 365-day year (schema section 7, X01).
    with pytest.raises(ConvertError, match="not a whole number of periods"):
        time_axis(604800.0, 53, startdate1=19790101, year=1979, calendar="gregorian")
    with pytest.raises(ConvertError, match="needs 12 records"):
        time_axis(-12, 11)
    with pytest.raises(ConvertError, match="needs startdate1"):
        time_axis(-1, 6)
    with pytest.raises(ConvertError, match="not valid"):
        time_axis(-7, 6, startdate1=19790101)
    with pytest.raises(ConvertError, match="startdate1 .* or start_time"):
        time_axis(86400.0, 3)
    with pytest.raises(ConvertError, match="needs pkg/cal dates"):
        time_axis(-12, 12, start_time=0.0)
    with pytest.raises(ConvertError, match="calendar"):
        time_axis(86400.0, 3, startdate1=19790101, calendar="julian")


# ---------------------------------------------------------------------------
# Synthetic grids


def latlon_grid(nx=12, ny=9):
    """30 x 10 degree cells from 40S; first column and one more cell are land."""
    lat = np.deg2rad(-40.0 + 10.0 * np.arange(ny + 1))
    rac1 = 6371.0e3 ** 2 * np.deg2rad(30.0) * (np.sin(lat[1:]) - np.sin(lat[:-1]))
    rac = np.repeat(rac1[:, None], nx, axis=1)
    hfac = np.ones((ny, nx))
    hfac[:, 0] = 0.0
    hfac[4, 5] = 0.0
    return rac, hfac


def exch2_grid(nx=192, ny=32):
    """cs32-shaped global array: irregular areas, a blank tile, some land."""
    rng = np.random.default_rng(11)
    rac = rng.uniform(1.0e9, 1.0e11, (ny, nx))
    hfac = np.ones((ny, nx))
    rac[:, 64:96] = 0.0          # a blank exch2 tile: every grid field is 0
    hfac[:, 64:96] = 0.0
    hfac[0:4, 0:10] = 0.0
    return rac, hfac


def test_latlon_one_source_per_cell(tmp_path):
    rac, hfac = latlon_grid()
    ny, nx = rac.shape
    rng = np.random.default_rng(2)
    dense = np.zeros((5, ny, nx))
    on = (hfac > 0) & (rng.uniform(size=hfac.shape) < 0.3)
    dense[:, on] = rng.uniform(1e-8, 1e-6, (5, int(on.sum())))
    dense[:, 2, 3] = 0.0                      # never any runoff: not a source
    dense[:, 6, 7] = [0.0, 0.0, 0.0, 4e-7, 0.0]   # runoff in one record only
    out = str(tmp_path / "ll.nc")
    assert dense_to_sparse(dense, out, rac=rac, hfac=hfac, prec=64, period=86400.0,
                           startdate1=20000101, calendar="noleap") == [out]
    d = read(out)
    cells = np.nonzero((dense != 0.0).any(axis=0).ravel())[0]
    assert 6 * nx + 7 in cells and 2 * nx + 3 not in cells
    assert np.array_equal(d["target_cell"], cells)
    assert np.array_equal(d["target_source"], np.arange(cells.size))
    assert np.all(d["target_fraction"] == 1.0)
    assert np.array_equal(d["target_cell_area"], rac.ravel()[cells])
    assert d["ids"][0] == "cell_{0:03d}".format(cells[0])
    assert d["attrs"]["mitgcm_grid_nx"] == nx and d["attrs"]["mitgcm_grid_ny"] == ny
    total = (dense * rac).reshape(5, -1).sum(axis=1)
    assert np.abs(d["runoff_flux"].sum(axis=1) / total - 1.0).max() < 1e-12
    back = sparse_to_dense(out).astype("f8")
    assert np.all(np.abs(back - dense) <= np.spacing(dense))
    assert_clean(check_files(out))
    # float32 input comes back exactly.
    d32 = dense.astype(">f4")
    out32 = str(tmp_path / "ll32.nc")
    dense_to_sparse(d32, out32, rac=rac, hfac=hfac, prec=32, period=86400.0,
                    startdate1=20000101, calendar="noleap")
    assert np.array_equal(sparse_to_dense(out32), d32)


def test_exch2_layout_with_groups_and_temperature(tmp_path):
    rac, hfac = exch2_grid()
    ny, nx = rac.shape
    area = rac.ravel()
    g = np.array([1.0, 0.5, 0.0, 2.0])                 # the groups stop in record 2
    alpha = {191 + nx * 31: 3.0e-7, 0 + nx * 31: 1.0e-7, 100 + nx * 5: 2.0e-7}
    beta = {10 + nx * 10: 5.0e-8, 11 + nx * 10: 1.5e-7}
    lone = {50 + nx * 20: [1e-7, 2e-7, 3e-7, 4e-7], 150 + nx * 0: [5e-8, 0.0, 6e-8, 0.0]}
    dense = np.zeros((4, ny * nx))
    temp = np.zeros((4, ny * nx))
    for cells in (alpha, beta):
        for n, (c, peak) in enumerate(cells.items()):
            dense[:, c] = peak * g
            temp[:, c] = 5.0 + 3.0 * n + np.arange(4)
    for c, series in lone.items():
        dense[:, c] = series
        temp[:, c] = [1.0, 2.0, 3.0, 4.0]
    groups = [("alpha", c) for c in alpha] + [("beta", c) for c in beta]
    out = str(tmp_path / "cs.nc")
    dense_to_sparse(dense.reshape(4, ny, nx), out, rac=rac, hfac=hfac, prec=64,
                    period=2592000.0, start_time=1296000.0, calendar="360_day",
                    temperature=temp.reshape(4, ny, nx), sources=groups)
    d = read(out)
    assert d["ids"] == ["cell_0150", "alpha", "beta", "cell_3890"]
    assert 191 + nx * 31 == 6143 and 6143 in d["target_cell"]
    for name, cells in (("alpha", alpha), ("beta", beta)):
        s = d["ids"].index(name)
        rows = d["target_source"] == s
        assert sorted(d["target_cell"][rows]) == sorted(cells)
        vol = np.array([cells[c] * area[c] for c in d["target_cell"][rows]])
        want = vol / vol.sum()
        assert np.abs(d["target_fraction"][rows] - want).max() < 1e-12
        assert abs(d["target_fraction"][rows].sum() - 1.0) < 1e-12
        assert np.abs(d["runoff_flux"][:, s] - vol.sum() * g).max() < 1e-12 * vol.sum()
        # Temperature: mean over the cells weighted by their share, in every
        # record, also in record 2 where the flux is zero.
        tcell = np.stack([temp[:, c] for c in d["target_cell"][rows]], axis=1)
        assert np.abs(d["runoff_temperature"][:, s] - tcell @ want).max() < 1e-12
    for c, series in lone.items():
        s = d["ids"].index("cell_{0:04d}".format(c))
        assert np.array_equal(d["runoff_flux"][:, s], np.array(series) * area[c])
        assert np.array_equal(d["runoff_temperature"][:, s], [1.0, 2.0, 3.0, 4.0])
    total = (dense * area).sum(axis=1)
    assert np.abs(d["runoff_flux"].sum(axis=1) / total - 1.0).max() < 1e-12
    back = sparse_to_dense(out).reshape(4, -1).astype("f8")
    assert np.abs(back - dense).max() <= 1e-14 * dense.max()
    assert np.array_equal(back != 0.0, dense != 0.0)
    # Grid checks R01 and R02 against the same grid written as model output.
    gdir = tmp_path / "grid"
    gdir.mkdir()
    write_mds(str(gdir / "RAC"), rac)
    write_mds(str(gdir / "hFacC"), hfac[None])
    assert_clean(check_files(out, grid_dir=str(gdir)))
    assert np.array_equal(sparse_to_dense(out, grid_dir=str(gdir)).reshape(4, -1), back)


def test_runoff_on_land_is_refused(tmp_path):
    rac, hfac = exch2_grid()
    dense = np.zeros((2, 32, 192))
    dense[0, 20, 50] = 1e-7
    dense[1, 3, 70] = 2e-7                  # in the blank tile
    timing = dict(period=86400.0, startdate1=20000101)
    with pytest.raises(ConvertError) as err:
        dense_to_sparse(dense, str(tmp_path / "x.nc"), rac=rac, hfac=hfac, prec=64,
                        **timing)
    text = str(err.value)
    assert "on land" in text and "cell 646 (i = 70, j = 3" in text and "record 2" in text
    assert not (tmp_path / "x.nc").exists()
    with pytest.raises(ConvertError, match="'delta'.*cell 1 .*on land"):
        dense_to_sparse(np.zeros((1, 32, 192)), str(tmp_path / "x.nc"), rac=rac,
                        hfac=hfac, sources=[("delta", 1)])
    dense[1, 3, 70] = np.nan
    with pytest.raises(ConvertError, match="nan.*cell 646.*non-finite"):
        dense_to_sparse(dense, str(tmp_path / "x.nc"), rac=rac, hfac=hfac, prec=64,
                        **timing)
    # A constant field uses record 1 only, so record 2 is not looked at.
    dense[1, 3, 70] = 2e-7
    with pytest.warns(UserWarning, match="exf uses 1 of the 2 records"):
        dense_to_sparse(dense, str(tmp_path / "x.nc"), rac=rac, hfac=hfac, prec=64)
    assert read(tmp_path / "x.nc")["target_cell"].tolist() == [50 + 192 * 20]
    with pytest.raises(ConvertError, match="zero everywhere"):
        dense_to_sparse(np.zeros((1, 32, 192)), str(tmp_path / "x.nc"), rac=rac, hfac=hfac)


def test_group_with_time_varying_shares(tmp_path):
    rac, hfac = exch2_grid()
    dense = np.zeros((3, 32 * 192))
    a, b = 5 + 192 * 4, 170 + 192 * 10          # cells 773 and 2090
    dense[:, a] = [1e-7, 2e-7, 3e-7]
    dense[:, b] = [3e-7, 2e-7, 1e-7]
    dense = dense.reshape(3, 32, 192)
    kw = dict(rac=rac, hfac=hfac, prec=64, period=86400.0, startdate1=20000101,
              sources=[("gamma", a), ("gamma", b)])
    with pytest.raises(ConvertError, match="'gamma'.*shares of the flux change in time"):
        dense_to_sparse(dense, str(tmp_path / "g.nc"), **kw)
    out = str(tmp_path / "g.nc")
    dense_to_sparse(dense, out, split_varying=True, **kw)
    d = read(out)
    assert d["ids"] == ["gamma_0773", "gamma_2090"]
    assert np.array_equal(d["target_cell"], [a, b]) and np.all(d["target_fraction"] == 1.0)
    assert np.array_equal(d["runoff_flux"],
                          dense.reshape(3, -1)[:, [a, b]] * rac.ravel()[[a, b]])
    assert_clean(check_files(out))
    # Shares that differ by less than share_tol count as constant.
    dense = dense.reshape(3, -1)
    dense[:, b] = dense[:, a] * np.array([3.0, 3.0 * (1 + 1e-11), 3.0])
    dense_to_sparse(dense.reshape(3, 32, 192), out, **kw)
    assert read(out)["ids"] == ["gamma"]


def test_sparse_to_dense_with_two_sources_on_one_cell(tmp_path):
    """Volumes add and temperature is the flux-weighted mean, by hand.

    Grid 5 x 4. Source 0 feeds cell 6 (fraction 0.25, area 3e9 m2) and cell 12
    (0.75, 2e9); source 1 feeds cell 12 (1.0, 2e9). Flux (m3/s) per record:
    [400, 100], [0, 0], [0, 50]; temperature: [2, 8], [3, 9], [4, 6].

    Cell 12: runoff (400*0.75 + 100)/2e9 = 2.0e-7, then 0, then 50/2e9 =
    2.5e-8 m/s. Temperature (300*2 + 100*8)/400 = 3.5; with no flux the
    weights are the fractions, (0.75*3 + 1*9)/1.75 = 45/7; then only source
    1 flows, 6. Cell 6 has one source: runoff 400*0.25/3e9, 0, 0 and
    temperature 2, 3, 4. Every other cell is 0, or the fill value.
    """
    path = str(tmp_path / "two.nc")
    with netCDF4.Dataset(path, "w") as ds:
        ds.setncatts({"mitgcm_runoff_schema_version": "1.0",
                      "mitgcm_grid_nx": np.int32(5), "mitgcm_grid_ny": np.int32(4),
                      "mitgcm_time_sampling": "fixed", "mitgcm_time_period": 86400.0})
        for name, size in (("time", 3), ("source", 2), ("target", 3)):
            ds.createDimension(name, size)
        v = ds.createVariable("time", "f8", ("time",))
        v.setncatts({"units": "days since 2000-01-01 00:00:00", "calendar": "noleap"})
        v[:] = [0.5, 1.5, 2.5]
        for name, dtype, dim, values in (
                ("target_source", "i4", ("target",), [0, 0, 1]),
                ("target_cell", "i4", ("target",), [6, 12, 12]),
                ("target_fraction", "f8", ("target",), [0.25, 0.75, 1.0]),
                ("target_cell_area", "f8", ("target",), [3.0e9, 2.0e9, 2.0e9]),
                ("runoff_flux", "f8", ("time", "source"),
                 [[400.0, 100.0], [0.0, 0.0], [0.0, 50.0]]),
                ("runoff_temperature", "f8", ("time", "source"),
                 [[2.0, 8.0], [3.0, 9.0], [4.0, 6.0]])):
            ds.createVariable(name, dtype, dim)[:] = values
    runoff = sparse_to_dense(path)
    assert runoff.dtype == np.dtype(">f8") and runoff.shape == (3, 4, 5)
    flat = runoff.reshape(3, 20).astype("f8")
    assert flat[:, 12] == pytest.approx([2.0e-7, 0.0, 2.5e-8], rel=1e-14, abs=0.0)
    assert flat[:, 6] == pytest.approx([100.0 / 3.0e9, 0.0, 0.0], rel=1e-14, abs=0.0)
    others = [c for c in range(20) if c not in (6, 12)]
    assert np.all(flat[:, others] == 0.0)
    # Volume: the sum of runoff times area is the sum of the source fluxes.
    assert flat[:, 12] * 2.0e9 + flat[:, 6] * 3.0e9 == pytest.approx(
        [500.0, 0.0, 50.0], rel=1e-14, abs=0.0)
    temp = sparse_to_dense(path, variable="runoff_temperature", fill=-999.0)
    flat = temp.reshape(3, 20).astype("f8")
    assert flat[:, 12] == pytest.approx([3.5, 45.0 / 7.0, 6.0], rel=1e-14, abs=0.0)
    assert np.array_equal(flat[:, 6], [2.0, 3.0, 4.0])
    assert np.all(flat[:, others] == -999.0)
    assert np.all(sparse_to_dense(path, variable="runoff_temperature")
                  .reshape(3, 20)[:, others] == 0.0)


def test_group_without_fractions_in_range_is_refused(tmp_path):
    """Negative runoff can leave a group with no fractions in [0, 1]."""
    rac, hfac = latlon_grid()
    a, b = 3 + 12 * 3, 4 + 12 * 3
    kw = dict(rac=rac, hfac=hfac, prec=64, period=86400.0, startdate1=20000101,
              sources=[("delta", a), ("delta", b)])
    out = str(tmp_path / "d.nc")
    # The two cells cancel in the one record: the group's flux sums to zero.
    dense = np.zeros((1, 9, 12))
    dense[0, 3, 3], dense[0, 3, 4] = 2e-7, -2e-7
    with pytest.warns(UserWarning, match="negative"):
        with pytest.raises(ConvertError, match="'delta'.*sums to zero over all records"):
            dense_to_sparse(dense, out, **kw)
    # Constant shares of 1.5 and -0.5: a fraction below 0.
    dense = np.zeros((2, 9, 12))
    dense[:, 3, 3], dense[:, 3, 4] = [3e-7, 6e-7], [-1e-7, -2e-7]
    with pytest.warns(UserWarning, match="negative"):
        with pytest.raises(ConvertError, match="'delta'.*opposite sign"):
            dense_to_sparse(dense, out, **kw)
    # split_varying gives each cell its own source, which is well defined.
    with pytest.warns(UserWarning, match="negative"):
        dense_to_sparse(dense, out, split_varying=True, **kw)
    d = read(out)
    assert d["ids"] == ["delta_039", "delta_040"] and np.all(d["target_fraction"] == 1.0)
    assert np.all(np.isfinite(d["runoff_flux"]))
    assert np.array_equal(sparse_to_dense(out).astype("f8"), dense)
    # A one-cell group has fraction 1 whatever its sign.
    dense[:, 3, 4] = 0.0
    dense[:, 3, 3] = [2e-7, -2e-7]
    with pytest.warns(UserWarning, match="negative"):
        dense_to_sparse(dense, out, **kw)
    assert read(out)["ids"] == ["delta"]


def test_negative_runoff_warns(tmp_path):
    rac, hfac = latlon_grid()
    dense = np.zeros((2, 9, 12))
    dense[:, 3, 3] = [1e-7, -2e-7]
    out = str(tmp_path / "neg.nc")
    with pytest.warns(UserWarning, match="negative in 1 values.*cell 39"):
        dense_to_sparse(dense, out, rac=rac, hfac=hfac, prec=64, period=86400.0,
                        startdate1=20000101)
    report = check_files(out)
    assert not report.errors and report.rules("W") == {"D03"}
    assert np.array_equal(sparse_to_dense(out)[:, 3, 3], [1e-7, -2e-7])


def test_extra_records_are_dropped_with_a_warning(tmp_path):
    rac, hfac = latlon_grid()
    dense = np.zeros((3, 9, 12))
    dense[:, 3, 3] = [1e-7, 2e-7, 3e-7]
    out = str(tmp_path / "c.nc")
    with pytest.warns(UserWarning, match="exf uses 1 of the 3 records"):
        dense_to_sparse(dense, out, rac=rac, hfac=hfac, prec=64, period=0.0)
    assert np.array_equal(read(out)["runoff_flux"], [[1e-7 * rac[3, 3]]])


def test_read_source_groups(tmp_path):
    f = tmp_path / "s.txt"
    f.write_text("# group i j cell lon\n\nriver 3 2 27 10.5\nriver 4 2\nglacier 0 0 0\n")
    assert convert.read_source_groups(str(f), 12, 9) == [
        ("river", 27), ("river", 28), ("glacier", 0)]
    assert convert.read_source_groups(
        str(LAB / "input.rnof_const" / "runoff_sources.txt"), 20, 16) == [
        ("baffin", 288), ("baffin", 289), ("baffin", 290), ("labrador", 147),
        ("labrador", 167), ("greenland", 233), ("newfound", 52)]
    for text, msg in (("river 3 2 26\n", "is not i . nx.j = 27"),
                      ("river 12 2\n", "outside the 12 x 9 grid"),
                      ("river 3\n", "expected 'source_id i j"),
                      ("a 1 1\nb 1 1\n", "already in source 'a'"),
                      ("bad/id 1 1\n", "not a valid source_id"),
                      ("# nothing\n", "no source cells")):
        f.write_text(text)
        with pytest.raises(ConvertError, match=msg):
            convert.read_source_groups(str(f), 12, 9)


def test_command_line(tmp_path, capsys):
    rac, hfac = latlon_grid()
    gdir = tmp_path / "grid"
    gdir.mkdir()
    write_mds(str(gdir / "RAC"), rac)
    write_mds(str(gdir / "hFacC"), np.stack([hfac, hfac]))
    dense = np.zeros((3, 9, 12), dtype=">f4")
    dense[:, 3, 3] = [1e-7, 2e-7, 3e-7]
    dense[:, 8, 11] = [4e-7, 0.0, 5e-7]
    dense.tofile(str(tmp_path / "runoff.bin"))
    out, back = str(tmp_path / "runoff.nc"), str(tmp_path / "back.bin")
    assert convert.main([str(tmp_path / "runoff.bin"), "-o", out, "--grid-dir", str(gdir),
                         "--period", "86400", "--startdate1", "20000101",
                         "--calendar", "noLeapYear"]) == 0
    assert "0 error" in capsys.readouterr().out
    assert read(out)["attrs"]["dense_precision"] == 32
    assert convert.main([out, "-o", back, "--to-dense"]) == 0
    assert (tmp_path / "back.bin").read_bytes() == (tmp_path / "runoff.bin").read_bytes()
    dense[0, 0, 0] = 1e-7                     # land
    dense.tofile(str(tmp_path / "land.bin"))
    assert convert.main([str(tmp_path / "land.bin"), "-o", out, "--grid-dir", str(gdir),
                         "--period", "86400", "--startdate1", "20000101"]) == 1
    assert "on land at cell 0 (i = 0, j = 0" in capsys.readouterr().err
    assert convert.main([str(tmp_path / "missing.bin"), "-o", out, "--grid-dir",
                         str(gdir)]) == 2


def test_lazy_exports():
    import MITgcmutils.runoff as pkg
    assert pkg.dense_to_sparse is convert.dense_to_sparse
    assert pkg.sparse_to_dense is convert.sparse_to_dense
    assert {"dense_to_sparse", "sparse_to_dense"} <= set(pkg.__all__)
