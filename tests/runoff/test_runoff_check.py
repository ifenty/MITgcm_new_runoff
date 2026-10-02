"""Tests of the sparse-runoff integrity checker and example writer (RUNOFF-001).

One battery covers every rule of schema section 9 (``docs/runoff_schema.md``):
the valid example is clean; each E rule is triggered by one targeted
corruption and the file is rejected by ``main()`` (exit 1); W rules warn and
exit 0 unless ``--strict``; I rules never fail. It also covers the
representative input classes: constant, monthly (leap February), 360_day
annual climatology, float32 fractions, the fraction-sum tolerance edge,
int64 cells, yearly file pairs, NETCDF3, JSON output, grid checks from
MITgcm-style grid files (tiled and global), and the streamed large case.
The ``python -m MITgcmutils.runoff.check`` entry point and the package's lazy
exports are exercised in subprocesses, with RuntimeWarning as an error.
Tables-only mode is checked on a file without time series (clean, with one
S10 finding), on a table fault (still reported) and a time-series fault (not
looked at), and on several files (tables compared, time order skipped).
"""

import json
import os
import subprocess
import sys

import netCDF4
import numpy as np
import pytest

from conftest import LAND_CELL, NX, ROOT, modify, write_mds
from MITgcmutils.runoff import check_files, schema, write_example
from MITgcmutils.runoff.check import MAX_DETAILS, main
from MITgcmutils.runoff.example import lab_sea_grid

EX_CELLS = np.array([69, 70, 125, 233, 234])


def build(tmp_path, overrides=None, modifier=None, name="runoff.nc"):
    p = write_example(str(tmp_path / name), **(overrides or {}))
    if modifier is not None:
        modify(p, modifier)
    return p


def setv(var, index, value):
    def fn(ds):
        ds.variables[var][index] = value
    return fn


def unwritten_record(ds):
    """Append record 4 to time and time_bnds only; the series stay unwritten."""
    ds.variables["time"][4] = 4.5
    ds.variables["time_bnds"][4, :] = [4.0, 5.0]


def packed(var, raw, **attrs):
    """Store ``raw`` values in ``var`` as-is, then add packing attributes."""
    def fn(ds):
        v = ds.variables[var]
        v.set_auto_maskandscale(False)
        if raw is not None:
            v[:] = raw
        for k, a in attrs.items():
            v.setncattr(k, a)
    return fn


def _clim_360(start_month=1):
    """A 12-month annual climatology on the 360_day calendar from ``start_month``."""
    e = (np.arange(13) + start_month - 1) * 30.0
    return dict(time=0.5 * (e[:-1] + e[1:]), time_bnds=np.stack([e[:-1], e[1:]], 1),
                time_sampling="monthly", time_period=None, calendar="360_day",
                time_repeat="annual")


def ncstring(var, att, value):
    """Rewrite one attribute as NC_STRING (``var=None``: global)."""
    def fn(ds):
        (ds if var is None else ds.variables[var]).setncattr_string(att, value)
    return fn


# ---------------------------------------------------------------------------
# Valid example


def test_example_is_clean(example):
    r = check_files(example)
    assert r.findings == [], r.format_text()
    assert main([example]) == 0
    assert main([example, "--strict"]) == 0


def test_example_contents(example):
    with netCDF4.Dataset(example) as ds:
        assert ds.data_model == "NETCDF4"
        assert {d: len(ds.dimensions[d]) for d in ("time", "source", "target", "alias",
                                                  "nv")} == \
            {"time": 4, "source": 3, "target": 5, "alias": 2, "nv": 2}
        assert ds.dimensions["time"].isunlimited()
        for name, (dims, cls, req) in schema.TABLE_VARIABLES.items():
            assert name in ds.variables, name
        for name in schema.TIMESERIES_VARIABLES + ("runoff_ptracer_dye",):
            v = ds.variables[name]
            assert v.chunking() == [1, 3]
            assert v.filters()["zlib"]
        for a in schema.RECOMMENDED_GLOBAL_ATTRS:
            assert a in ds.ncattrs(), a
        assert ds.mitgcm_runoff_schema_version == schema.SCHEMA_VERSION
        assert (ds.mitgcm_grid_nx, ds.mitgcm_grid_ny) == (20, 16)
        # glacier temperature is the fill value (= surface temperature)
        t = ds.variables["runoff_temperature"]
        t.set_auto_mask(False)
        assert np.all(t[:, 2] == t._FillValue)


def test_temperature_nan_is_allowed(tmp_path):
    p = build(tmp_path, modifier=setv("runoff_temperature", (1, 0), np.nan))
    assert check_files(p).findings == []


# ---------------------------------------------------------------------------
# E rules: one targeted corruption each, rejected with exit status 1

F4_FILL = netCDF4.default_fillvals["f4"]
ZEROS = np.zeros((4, 3), dtype="f4")

E_CASES = [
    pytest.param("S01", dict(format="NETCDF3_64BIT_OFFSET"), None, "runoff.nc",
                 id="S01-netcdf3"),
    pytest.param("S02", dict(global_attrs={"mitgcm_runoff_schema_version": "2.0"}),
                 None, "runoff.nc", id="S02-major"),
    pytest.param("S02", dict(global_attrs={"mitgcm_runoff_schema_version": None}),
                 None, "runoff.nc", id="S02-missing"),
    pytest.param("S03", dict(id_strlen=65), None, "runoff.nc", id="S03-strlen"),
    pytest.param("S03", dict(target_source=None, target_cell=None,
                             target_fraction=None, target_level=None),
                 None, "runoff.nc", id="S03-empty-target"),
    pytest.param("S04", dict(target_fraction=None), None, "runoff.nc",
                 id="S04-missing"),
    pytest.param("S04", dict(dtypes={"target_cell": "f8"}), None, "runoff.nc",
                 id="S04-type"),
    pytest.param("S04", dict(runoff_flux=None), None, "runoff.nc", id="S04-flux"),
    pytest.param("S04", dict(dtypes={"time": "f4"}), None, "runoff.nc",
                 id="S04-float32-time"),
    pytest.param("S04", dict(dtypes={"time_bnds": "f4"}), None, "runoff.nc",
                 id="S04-float32-time_bnds"),
    pytest.param("S05", dict(extra_vars={"runoff_temprature": (
        ("time", "source"), ZEROS, {"units": "degC"})}), None, "runoff.nc",
        id="S05-var"),
    pytest.param("S05", dict(global_attrs={"mitgcm_grid_nz": 15}), None, "runoff.nc",
                 id="S05-attr"),
    pytest.param("S07", None, packed("runoff_flux", None, scale_factor=np.float32(0.001)),
                 "runoff.nc", id="S07-flux-scale_factor"),
    pytest.param("S07", None, packed("target_fraction", None, add_offset=0.0),
                 "runoff.nc", id="S07-fraction-add_offset"),
    pytest.param("S07", None, packed("time", None, scale_factor=1.0), "runoff.nc",
                 id="S07-time-scale_factor"),
    pytest.param("S08", None, ncstring(None, "mitgcm_time_sampling", "fixed"),
                 "runoff.nc", id="S08-global-mitgcm"),
    pytest.param("S08", None, ncstring("time", "units", "days since 2000-01-01 00:00:00"),
                 "runoff.nc", id="S08-time-units"),
    pytest.param("S08", None, ncstring("time", "calendar", "standard"), "runoff.nc",
                 id="S08-time-calendar"),
    pytest.param("S08", None, ncstring("runoff_flux", "units", "m3 s-1"), "runoff.nc",
                 id="S08-runoff-units"),
    pytest.param("G01", dict(global_attrs={"mitgcm_grid_nx": 0}), None, "runoff.nc",
                 id="G01-zero"),
    pytest.param("G01", dict(global_attrs={"mitgcm_grid_ny": 16.0}), None, "runoff.nc",
                 id="G01-float"),
    pytest.param("G01", dict(nx=None), None, "runoff.nc", id="G01-missing"),
    pytest.param("I01", dict(source_id=["churchill labrador", "koksoak", "jakobshavn"]),
                 None, "runoff.nc", id="I01-space"),
    pytest.param("I01", dict(source_id=["_churchill", "koksoak", "jakobshavn"]),
                 None, "runoff.nc", id="I01-start"),
    pytest.param("I01", dict(source_id=["a" * 65, "koksoak", "jakobshavn"]),
                 None, "runoff.nc", id="I01-long"),
    pytest.param("I02", dict(source_id=["koksoak", "koksoak", "jakobshavn"]),
                 None, "runoff.nc", id="I02"),
    pytest.param("A01", dict(alias_source=[0, 5]), None, "runoff.nc", id="A01-range"),
    pytest.param("A01", dict(alias_name=["Grand River", ""]), None, "runoff.nc",
                 id="A01-empty"),
    pytest.param("T01", dict(target_source=[0, 0, 1, 2, 7]), None, "runoff.nc", id="T01"),
    pytest.param("T02", dict(target_cell=[69, 70, 125, 233, 320]), None, "runoff.nc",
                 id="T02"),
    pytest.param("T03", dict(target_cell=[69, 69, 125, 233, 234]), None, "runoff.nc",
                 id="T03"),
    pytest.param("T04", dict(target_fraction=[0.7, 0.3, 1.0, 1.5, -0.5]), None,
                 "runoff.nc", id="T04"),
    pytest.param("T04", dict(target_fraction=[0.7, 0.3, np.nan, 0.5, 0.5]), None,
                 "runoff.nc", id="T04-nan"),
    pytest.param("T05", dict(target_fraction=[0.7, 0.3, 1.0, 0.5, 0.49]), None,
                 "runoff.nc", id="T05-sum"),
    pytest.param("T05", dict(target_source=[0, 0, 0, 2, 2],
                             target_fraction=[0.5, 0.3, 0.2, 0.5, 0.5]), None,
                 "runoff.nc", id="T05-no-targets"),
    pytest.param("T07", dict(target_level=[1, 1, 1, 2, 1]), None, "runoff.nc", id="T07"),
    pytest.param("M01", dict(time_units="days after 2000-01-01"), None, "runoff.nc",
                 id="M01-units"),
    pytest.param("M01", dict(time_units="months since 2000-01-01"), None, "runoff.nc",
                 id="M01-months"),
    pytest.param("M01", dict(calendar="julian"), None, "runoff.nc", id="M01-calendar"),
    pytest.param("M01", dict(time_units="days since 2000-13-01"), None, "runoff.nc",
                 id="M01-date"),
    pytest.param("M01", dict(var_attrs={"time_bnds": {"units": "hours since 2000-01-01"}}),
                 None, "runoff.nc", id="M01-bnds-units"),
    pytest.param("M03", dict(time=[0.5, 1.5, 1.5, 3.5],
                             time_bnds=[[0, 1], [1, 2], [1, 2], [3, 4]]),
                 None, "runoff.nc", id="M03-not-increasing"),
    pytest.param("M03", None, setv("time", 2, np.nan), "runoff.nc", id="M03-nan"),
    pytest.param("M04", dict(time_bnds=None), None, "runoff.nc", id="M04-missing"),
    pytest.param("M04", dict(time_bnds=[[0, 1], [1, 2], [2.1, 3], [3, 4]]), None,
                 "runoff.nc", id="M04-gap"),
    pytest.param("M04", dict(time_bnds=[[0, 1], [1, 2], [2, 2.4], [2.4, 4]]), None,
                 "runoff.nc", id="M04-contain"),
    pytest.param("M05", dict(global_attrs={"mitgcm_time_period": 3600.0}), None,
                 "runoff.nc", id="M05-period"),
    pytest.param("M05", dict(time_period=None), None, "runoff.nc",
                 id="M05-period-missing"),
    pytest.param("M05", dict(time_sampling="daily"), None, "runoff.nc",
                 id="M05-sampling"),
    pytest.param("M05", dict(time_sampling=None), None, "runoff.nc",
                 id="M05-sampling-missing"),
    pytest.param("M05", dict(time_sampling="constant"), None, "runoff.nc",
                 id="M05-constant-4-records"),
    pytest.param("M05", dict(time_repeat="weekly"), None, "runoff.nc", id="M05-repeat"),
    pytest.param("M05", dict(time=[0.0], time_sampling="constant", time_period=None,
                             time_repeat="annual"), None, "runoff.nc",
                 id="M05-annual-single-record-no-bounds"),
    pytest.param("M06", None, None, "runoff_2001.nc", id="M06"),
    pytest.param("D01", dict(var_attrs={"runoff_flux": {"units": "kg s-1"}}), None,
                 "runoff.nc", id="D01-units"),
    pytest.param("D01", dict(var_attrs={"runoff_flux": {"units": None}}), None,
                 "runoff.nc", id="D01-no-units"),
    pytest.param("D01", dict(dtypes={"runoff_salinity": "i4"}), None, "runoff.nc",
                 id="D01-type"),
    pytest.param("D01", dict(runoff_temperature=None, extra_vars={"runoff_temperature": (
        ("source", "time"), np.zeros((3, 4), "f4"), {"units": "degC"})}), None,
        "runoff.nc", id="D01-dims"),
    pytest.param("D02", None, setv("runoff_flux", (2, 1), np.nan), "runoff.nc",
                 id="D02-nan"),
    pytest.param("D02", None, setv("runoff_flux", (0, 0), np.inf), "runoff.nc",
                 id="D02-inf"),
    pytest.param("D02", None, setv("runoff_flux", (3, 2), F4_FILL), "runoff.nc",
                 id="D02-default-fill"),
    pytest.param("D02", dict(fill_values={"runoff_flux": -999.0}),
                 setv("runoff_flux", (1, 1), -999.0), "runoff.nc", id="D02-fillvalue"),
    pytest.param("D02", dict(var_attrs={"runoff_flux": {
        "missing_value": np.float32(-1e20)}}),
        setv("runoff_flux", (1, 2), -1e20), "runoff.nc", id="D02-missing-value"),
    pytest.param("D02", None, unwritten_record, "runoff.nc", id="D02-unwritten-record"),
    pytest.param("D05", None, setv("runoff_salinity", (0, 0), -1.0), "runoff.nc",
                 id="D05-negative"),
    pytest.param("D05", None, setv("runoff_salinity", (0, 0), np.nan), "runoff.nc",
                 id="D05-nan"),
    pytest.param("D07", dict(ptracers={"dye": ("auto", "")}), None, "runoff.nc",
                 id="D07-empty-units"),
    pytest.param("D07", dict(ptracers={"bad-name": ("auto", "mol m-3")}), None,
                 "runoff.nc", id="D07-name"),
    pytest.param("D07", None, setv("runoff_ptracer_dye", (3, 0), np.nan), "runoff.nc",
                 id="D07-missing"),
    pytest.param("U01", dict(var_attrs={"target_fraction": {"units": "percent"}}), None,
                 "runoff.nc", id="U01-fraction"),
    pytest.param("U01", dict(var_attrs={"target_cell": {"units": "1"}}), None,
                 "runoff.nc", id="U01-index"),
    pytest.param("U01", dict(var_attrs={"source_lon": {"units": "degrees"}}), None,
                 "runoff.nc", id="U01-lon"),
    pytest.param("U01", dict(var_attrs={"target_cell_area": {"units": "km2"}}), None,
                 "runoff.nc", id="U01-area"),
    pytest.param("U01", dict(var_attrs={"target_fraction": {"units": None}}), None,
                 "runoff.nc", id="U01-missing-fraction-units"),
    pytest.param("U01", dict(var_attrs={"target_lat": {"units": None}}), None,
                 "runoff.nc", id="U01-missing-lat-units"),
    pytest.param("U01", dict(var_attrs={"alias_source": {"units": "1"}}), None,
                 "runoff.nc", id="U01-units-on-alias-index"),
    pytest.param("D09", None, setv("runoff_temperature", (2, 0), -np.inf), "runoff.nc",
                 id="D09-inf-temperature"),
    pytest.param("D09", dict(fill_values={"runoff_temperature": np.inf}), None,
                 "runoff.nc", id="D09-inf-fillvalue"),
    pytest.param("D09", dict(var_attrs={"runoff_temperature": {
        "missing_value": np.float32(-np.inf)}}), None, "runoff.nc",
        id="D09-inf-missing_value"),
    pytest.param("M05", dict(time=[0.0, 31.0, 60.0, 91.0],
                             time_bnds=[[0, 31], [31, 60], [60, 91], [91, 121]],
                             time_sampling="monthly", time_period=None), None,
                 "runoff.nc", id="M05-monthly-time-at-month-start"),
    # Correction round 2
    pytest.param("S08", None, lambda ds: ds.variables["runoff_ptracer_dye"].setncattr(
        "units", b"\xc2\xb5mol kg-1"), "runoff.nc", id="S08-non-ascii-units"),
    pytest.param("S09", None, lambda ds: ds.variables["runoff_flux"].setncattr(
        "missing_value", "-999"), "runoff.nc", id="S09-text-missing_value"),
    pytest.param("S09", None, lambda ds: ds.variables["runoff_flux"].setncattr(
        "missing_value", np.float64(-999.0)), "runoff.nc", id="S09-double-on-float"),
    pytest.param("M05", dict(_clim_360(start_month=7)), None, "runoff.nc",
                 id="M05-monthly-climatology-from-july"),
]


@pytest.mark.parametrize("rule, overrides, modifier, name", E_CASES)
def test_error_rule_fires(tmp_path, rule, overrides, modifier, name):
    p = build(tmp_path, overrides, modifier, name)
    r = check_files(p)
    assert rule in r.rules("E"), r.format_text()
    assert main([p]) == 1


# ---------------------------------------------------------------------------
# W rules: warn, exit 0, exit 1 with --strict

W_CASES = [
    pytest.param("I03", dict(source_id=["Koksoak", "koksoak", "jakobshavn"]), None,
                 id="I03"),
    pytest.param("I04", dict(source_type=["river", "lake", "glacier"]), None, id="I04"),
    pytest.param("A02", dict(alias_source=[2, 2],
                             alias_name=["Sermeq Kujalleq", "Sermeq Kujalleq"]),
                 None, id="A02"),
    pytest.param("T06", dict(target_fraction=[1.0, 0.0, 1.0, 0.5, 0.5]), None, id="T06"),
    pytest.param("M02", dict(calendar=None), None, id="M02"),
    pytest.param("D03", None, setv("runoff_flux", (1, 0), -5.0), id="D03"),
    pytest.param("D04", None, setv("runoff_temperature", (0, 0), 45.0), id="D04-hot"),
    pytest.param("D04", None, setv("runoff_temperature", (0, 1), -3.0), id="D04-cold"),
    pytest.param("D06", None, setv("runoff_salinity", (2, 1), 50.0), id="D06"),
    pytest.param("D08", None, setv("runoff_ptracer_dye", (1, 1), -0.1), id="D08"),
    pytest.param("P01", dict(chunk_time=2), None, id="P01"),
]


@pytest.mark.parametrize("rule, overrides, modifier", W_CASES)
def test_warning_rule_fires(tmp_path, rule, overrides, modifier):
    p = build(tmp_path, overrides, modifier)
    r = check_files(p)
    assert rule in r.rules("W"), r.format_text()
    assert r.errors == [], r.format_text()
    assert main([p]) == 0
    assert main([p, "--strict"]) == 1


I_CASES = [
    pytest.param("S06", dict(global_attrs={"title": None, "license": None}), id="S06"),
    pytest.param("T08", dict(target_source=[1, 0, 0, 2, 2],
                             target_cell=[125, 69, 70, 233, 234],
                             target_fraction=[1.0, 0.7, 0.3, 0.5, 0.5]), id="T08"),
]


@pytest.mark.parametrize("rule, overrides", I_CASES)
def test_info_rule_fires_and_never_fails(tmp_path, rule, overrides):
    p = build(tmp_path, overrides)
    r = check_files(p)
    assert rule in r.rules("I"), r.format_text()
    assert r.errors == [] and r.warnings == [], r.format_text()
    assert main([p, "--strict"]) == 0


# ---------------------------------------------------------------------------
# Messages name file, variable, source id and time


def test_messages_name_file_variable_source_and_time(tmp_path):
    p = build(tmp_path, modifier=setv("runoff_flux", (2, 1), np.nan))
    f, = [x for x in check_files(p).errors if x.rule == "D02"]
    assert f.message.startswith(p + ": runoff_flux: ")
    assert "source 'koksoak' (index 1)" in f.message
    assert "time=2.5 days since 2000-01-01 00:00:00 (2000-01-03 12:00:00)" in f.message
    assert (f.file, f.variable, f.source_id, f.source_index, f.record, f.time) == \
        (p, "runoff_flux", "koksoak", 1, 2, 2.5)

    p = build(tmp_path, dict(target_fraction=[0.7, 0.3, 1.0, 0.5, 0.49]),
              name="sum.nc")
    f, = [x for x in check_files(p).errors if x.rule == "T05"]
    assert "source 'jakobshavn' (index 2)" in f.message and "target_fraction" in f.message
    assert f.source_id == "jakobshavn"


def test_many_findings_are_capped_with_a_total(tmp_path):
    p = build(tmp_path, modifier=setv("runoff_flux", (slice(None), slice(None)), np.nan))
    d02 = [x for x in check_files(p).findings if x.rule == "D02"]
    assert len(d02) == min(12, MAX_DETAILS) + (1 if 12 > MAX_DETAILS else 0)
    n = 3000
    p = build(tmp_path, dict(time=np.arange(n) + 0.5), name="big.nc",
              modifier=setv("runoff_flux", (slice(None), slice(None)), np.nan))
    d02 = [x for x in check_files(p).findings if x.rule == "D02"]
    assert len(d02) == MAX_DETAILS + 1
    assert "{0} more D02 findings not listed ({1} in total)".format(
        3 * n - MAX_DETAILS, 3 * n) in d02[-1].message


# ---------------------------------------------------------------------------
# Representative input classes


def test_constant_single_record_without_bounds(tmp_path):
    p = build(tmp_path, dict(time=[0.0], time_sampling="constant", time_period=None))
    with netCDF4.Dataset(p) as ds:
        assert "time_bnds" not in ds.variables and len(ds.dimensions["time"]) == 1
    assert check_files(p).findings == []


MONTH_EDGES_2000 = [0, 31, 60, 91, 121]          # Jan..Apr 2000, leap February


def _monthly(edges):
    e = np.asarray(edges, dtype=float)
    return dict(time=0.5 * (e[:-1] + e[1:]), time_bnds=np.stack([e[:-1], e[1:]], 1),
                time_sampling="monthly", time_period=None)


def test_monthly_gregorian_leap_february(tmp_path):
    p = build(tmp_path, dict(_monthly(MONTH_EDGES_2000), calendar="gregorian"))
    assert check_files(p).findings == []
    # 28-day February in a leap year is not the calendar month
    p = build(tmp_path, dict(_monthly([0, 31, 59, 90, 120]), calendar="gregorian"),
              name="bad.nc")
    r = check_files(p)
    assert "M05" in r.rules("E")
    assert any("2000-02" in f.message for f in r.errors if f.rule == "M05")


def test_monthly_annual_climatology_360_day(tmp_path):
    clim = dict(_monthly(np.arange(13) * 30.0), calendar="360_day", time_repeat="annual")
    p = build(tmp_path, clim)
    assert check_files(p).findings == []
    short = dict(_monthly(np.arange(12) * 30.0), calendar="360_day", time_repeat="annual")
    r = check_files(build(tmp_path, short, name="short.nc"))
    assert "M05" in r.rules("E")


def test_float32_fractions_within_tolerance(tmp_path):
    p = build(tmp_path, dict(dtypes={"target_fraction": "f4"},
                             target_fraction=[0.7, 0.3, 1.0, 1 / 3, 2 / 3]))
    with netCDF4.Dataset(p) as ds:
        assert ds.variables["target_fraction"].dtype == np.float32
    assert check_files(p).findings == []


@pytest.mark.parametrize("value, ok", [(1 - 2e-6, False), (1 - 5e-7, True)])
def test_fraction_sum_tolerance_edge(tmp_path, value, ok):
    p = build(tmp_path, dict(target_fraction=[0.7, 0.3, value, 0.5, 0.5]))
    r = check_files(p)
    if ok:
        assert r.findings == [], r.format_text()
    else:
        assert r.rules("E") == {"T05"}
        assert r.errors[0].source_id == "koksoak"


def test_int64_target_cell(tmp_path):
    p = build(tmp_path, dict(dtypes={"target_cell": "i8"}))
    with netCDF4.Dataset(p) as ds:
        assert ds.variables["target_cell"].dtype == np.int64
    assert check_files(p).findings == []


def test_netcdf4_classic_with_char_strings_is_clean(tmp_path):
    p = build(tmp_path, dict(format="NETCDF4_CLASSIC"))
    assert check_files(p).findings == []


def test_netcdf3_reports_s01_and_still_checks(tmp_path):
    p = build(tmp_path, dict(format="NETCDF3_64BIT_OFFSET",
                             target_fraction=[0.7, 0.3, 1.0, 0.5, 0.49]))
    r = check_files(p)
    assert {"S01", "T05"} <= r.rules("E")


def test_inf_temperature_is_d09_not_d04(tmp_path):
    p = build(tmp_path, modifier=setv("runoff_temperature", (1, 1), np.inf))
    r = check_files(p)
    assert r.rules() == {"D09"}, r.format_text()
    f, = r.errors
    assert (f.source_id, f.record) == ("koksoak", 1) and "+Inf" in f.message


def test_calendar_matched_ignoring_case(tmp_path):
    p = build(tmp_path, dict(calendar="Gregorian"))
    assert check_files(p).findings == []
    p = build(tmp_path, dict(calendar="NOLEAP"), name="noleap.nc")
    assert check_files(p).findings == []


def test_user_lon_lat_variables_are_not_unit_checked(tmp_path):
    p = build(tmp_path, dict(extra_vars={
        "source_gauge_lon": (("source",), np.array([1.0, 2.0, 3.0]), {"units": "m"}),
        "source_gauge_lat": (("source",), np.array([1.0, 2.0, 3.0]), {})}))
    assert check_files(p).findings == []


# ---------------------------------------------------------------------------
# Correction round 1: packing (S07), Inf fill (D09), NC_STRING (S08), midpoints


def test_packed_flux_fill_is_found_as_stored(tmp_path):
    """Richard A witness a4: a packed flux hid its _FillValue (-1e30 * 0.001)."""
    def fn(ds):
        v = ds.variables["runoff_flux"]
        v.set_auto_maskandscale(False)               # store the fill value as-is
        v[1, 1] = np.float32(-1e30)
        v.setncattr("scale_factor", np.float32(0.001))
    p = build(tmp_path, dict(fill_values={"runoff_flux": np.float32(-1e30)}), fn)
    r = check_files(p)
    assert {"S07", "D02"} <= r.rules("E"), r.format_text()
    f, = [x for x in r.errors if x.rule == "D02"]
    assert (f.source_id, f.record) == ("koksoak", 1)
    assert "fill/missing value -1.00000002e+30" in f.message   # float32(-1e30)
    assert main([p]) == 1


def test_packed_fraction_is_checked_as_stored(tmp_path):
    """Richard A witness a5: stored fractions sum to 2, unpacked (x 0.5) to 1."""
    raw = 2.0 * np.array([0.7, 0.3, 1.0, 0.5, 0.5])
    p = build(tmp_path, modifier=packed("target_fraction", raw, scale_factor=0.5))
    r = check_files(p)
    assert {"S07", "T05"} <= r.rules("E"), r.format_text()
    assert main([p]) == 1


def test_packed_target_lon_is_not_s07(tmp_path):
    """target_lon is not model-read (schema section 1), so packing it is allowed."""
    p = build(tmp_path, modifier=packed("target_lon", None, scale_factor=1.0))
    with netCDF4.Dataset(p) as ds:
        assert "scale_factor" in ds.variables["target_lon"].ncattrs()
    r = check_files(p)
    assert r.findings == [], r.format_text()


def test_s08_is_a_warning_when_libnetcdf_cannot_be_loaded(tmp_path, monkeypatch):
    from MITgcmutils.runoff import check as C

    def broken_loader():
        raise OSError("libnetcdf not found (test)")
    monkeypatch.setattr(C, "_libnetcdf", broken_loader)
    # The NC_STRING attribute would be E S08; unchecked, it is only W S08.
    p = build(tmp_path, modifier=ncstring(None, "mitgcm_time_sampling", "fixed"))
    r = check_files(p)
    assert r.rules("E") == set() and r.rules("W") == {"S08"}, r.format_text()
    f, = r.warnings
    assert f.level == "W" and "attribute types not checked" in f.message
    assert main([p]) == 0
    assert main([p, "--strict"]) == 1


def test_unpacked_user_variable_is_not_s07(tmp_path):
    p = build(tmp_path, dict(extra_vars={"source_drainage_area": (
        ("source",), np.array([1.0, 2.0, 3.0]), {"units": "m2", "scale_factor": 1e6})}))
    assert "S07" not in check_files(p).rules()


def test_inf_fillvalue_temperature_is_d09(tmp_path):
    """Richard A witness d4: _FillValue = +Inf on the temperature, used in the data."""
    p = build(tmp_path, dict(fill_values={"runoff_temperature": np.inf}))
    r = check_files(p)
    assert r.rules("E") == {"D09"}, r.format_text()
    assert any("_FillValue = [inf] is infinite" in f.message for f in r.errors)
    assert any(f.source_id == "jakobshavn" and "+Inf" in f.message for f in r.errors)
    assert main([p]) == 1 and main([p, "--strict"]) == 1


@pytest.mark.parametrize("sign", [1, -1], ids=["+inf", "-inf"])
def test_inf_missing_value_temperature_is_d09(tmp_path, sign):
    """missing_value = +/-Inf on the temperature is D09 even with no Inf in the data."""
    def fn(ds):
        v = ds.variables["runoff_temperature"]
        v.setncattr("missing_value", v.dtype.type(sign * np.inf))
    p = build(tmp_path, modifier=fn)
    r = check_files(p)
    assert r.rules("E") == {"D09"} and r.warnings == [], r.format_text()
    f, = r.errors
    assert f.variable == "runoff_temperature"
    assert "missing_value = [{0}inf] is infinite".format("-" if sign < 0 else "") in f.message
    assert main([p]) == 1


def test_ncstring_model_attributes_are_s08(tmp_path):
    """Richard B witness example_ncstring_attrs: NC_STRING time/mitgcm attributes."""
    def fn(ds):
        ds.setncattr_string("mitgcm_runoff_schema_version", "1.0")
        ds.variables["time"].setncattr_string("units", "days since 2000-01-01 00:00:00")
    p = build(tmp_path, modifier=fn)
    r = check_files(p)
    assert r.rules("W") == set(), r.format_text()      # types were checked
    assert r.rules("E") == {"S08"}, r.format_text()
    assert {f.variable for f in r.errors} == {None, "time"}
    assert main([p]) == 1


def test_ncstring_on_attributes_the_model_does_not_read_is_fine(tmp_path):
    def fn(ds):
        ds.setncattr_string("title", "Example")
        ds.variables["target_lon"].setncattr_string("long_name", "cell-center longitude")
    p = build(tmp_path, modifier=fn)
    r = check_files(p)
    assert r.findings == [], r.format_text()


def test_example_writes_char_attributes(example):
    from MITgcmutils.runoff.check import _attr_types
    queries = [(None, a) for a in ("mitgcm_runoff_schema_version", "mitgcm_time_sampling",
                                   "mitgcm_time_repeat", "mitgcm_grid_name")]
    queries += [("time", "units"), ("time", "calendar")]
    queries += [(v, "units") for v in ("runoff_flux", "runoff_temperature",
                                       "runoff_salinity", "runoff_ptracer_dye")]
    types = _attr_types(example, queries)
    assert types is not None and set(types) == set(queries)
    assert set(types.values()) == {schema.NC_CHAR}


def test_monthly_time_must_be_the_midpoint(tmp_path):
    """Richard B witness monthly_start_of_month: time at the start of each month."""
    e = np.asarray(MONTH_EDGES_2000, dtype=float)
    p = build(tmp_path, dict(_monthly(MONTH_EDGES_2000), time=e[:-1] + 0.0))
    r = check_files(p)
    assert r.rules("E") == {"M05"}, r.format_text()
    assert len(r.errors) == 4 and all("midpoint" in f.message for f in r.errors)
    assert main([p]) == 1


def test_yearly_sampling_time_must_be_the_midpoint(tmp_path):
    edges = [0.0, 366.0, 731.0]                    # 2000 and 2001
    good = dict(time=[183.0, 548.5], time_bnds=[[0, 366], [366, 731]],
                time_sampling="yearly", time_period=None)
    assert check_files(build(tmp_path, good)).findings == []
    bad = dict(good, time=edges[:-1])
    r = check_files(build(tmp_path, bad, name="bad.nc"))
    assert r.rules("E") == {"M05"}, r.format_text()


def test_schema_doc_xarray_recipe_writes_a_valid_file(tmp_path, monkeypatch):
    """The ```python block of schema section 11 runs and passes the checker."""
    import re
    pytest.importorskip("xarray")
    doc = (ROOT / "docs" / "runoff_schema.md").read_text(encoding="utf-8")
    section = doc.split("## 11. Writing a file with xarray", 1)[1]
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    monkeypatch.chdir(tmp_path)
    exec(compile(code, "docs/runoff_schema.md#11", "exec"), {"__name__": "__recipe__"})
    r = check_files(str(tmp_path / "runoff.nc"))
    assert r.errors == [] and r.warnings == [], r.format_text()
    assert r.rules() <= {"S06"}


# ---------------------------------------------------------------------------
# Several files (X01) and yearly file names (M06)


DAYS_IN_YEAR = {2000: 366, 2001: 365, 2002: 365}


def _year_file(tmp_path, year, first_day=0, ndays=None, name=None, **kw):
    """Daily file ``runoff_<year>.nc`` from day ``first_day`` for ``ndays`` days.

    The default covers the whole year, so consecutive years are continuous.
    """
    if ndays is None:
        ndays = DAYS_IN_YEAR[year] - first_day
    return build(tmp_path, dict(dict(time_units="days since {0}-01-01".format(year),
                                     time=first_day + np.arange(ndays) + 0.5), **kw),
                 name=name or "runoff_{0}.nc".format(year))


def _year_pair(tmp_path, **second):
    """Continuous full-year daily files for 2000 and 2001 (``second`` edits 2001)."""
    return _year_file(tmp_path, 2000), _year_file(tmp_path, 2001, **second)


def test_yearly_pair_passes(tmp_path):
    a, b = _year_pair(tmp_path)
    r = check_files([a, b])
    assert r.findings == [], r.format_text()
    assert main([a, b]) == 0


def test_x01_yearly_file_starting_a_day_late(tmp_path):
    """Richard B witness yr_runoff_2001/2002: 2002 starts on 2 January."""
    a = _year_file(tmp_path, 2001)
    b = _year_file(tmp_path, 2002, first_day=1)
    r = check_files([a, b])
    assert r.rules("E") == {"X01"}, r.format_text()
    msgs = " ".join(f.message for f in r.errors)
    assert "a gap of 86400 s" in msgs and "share one start offset" in msgs
    assert main([a, b]) == 1


def test_x01_gap_between_yearly_files(tmp_path):
    """Richard B witness gap_runoff_2003/2004: a gap, with equal start offsets."""
    a = _year_file(tmp_path, 2000, ndays=301)       # ends 2000-10-28
    b = _year_file(tmp_path, 2001)
    r = check_files([a, b])
    assert r.rules("E") == {"X01"}, r.format_text()
    f, = r.errors
    assert "a gap of" in f.message and "(65 days)" in f.message
    assert main([a, b]) == 1


def test_x01_continuous_but_shifted_start_offset(tmp_path):
    """Continuous at the file boundary, but 2000 starts on 2 January."""
    a = _year_file(tmp_path, 2000, first_day=1)     # 2000-01-02 .. 2001-01-01
    b = _year_file(tmp_path, 2001)
    r = check_files([a, b])
    assert r.rules("E") == {"X01"}, r.format_text()
    f, = r.errors
    assert "share one start offset" in f.message and "gap" not in f.message


def test_x01_multi_file_set_needs_time_bnds(tmp_path):
    one = dict(time=[0.5], time_bnds=None, time_sampling="constant", time_period=None)
    a = build(tmp_path, dict(one), name="a.nc")
    b = build(tmp_path, dict(one, time_units="days since 2000-01-02"), name="b.nc")
    r = check_files([a, b])
    assert r.rules("E") == {"X01"}, r.format_text()
    assert any("needs time_bnds" in f.message for f in r.errors)


def test_yearly_pair_with_different_targets_fails_x01(tmp_path):
    a, b = _year_pair(tmp_path, target_cell=[69, 70, 125, 233, 235])
    r = check_files([a, b])
    assert r.rules("E") == {"X01"}, r.format_text()
    assert any(f.variable == "target_cell" and "index 4" in f.message
               for f in r.errors)
    assert main([a, b]) == 1


def test_x01_variable_set_grid_and_order(tmp_path):
    a, b = _year_pair(tmp_path, runoff_salinity=None)
    r = check_files([a, b])
    assert any("variable set differs" in f.message for f in r.errors if f.rule == "X01")
    a, b = _year_pair(tmp_path, global_attrs={"mitgcm_grid_name": "other"})
    assert "X01" in check_files([a, b]).rules("E")
    a, b = _year_pair(tmp_path)
    r = check_files([b, a])          # listed out of time order
    assert r.rules("E") == {"X01"}
    same_a = build(tmp_path, name="a.nc")
    same_b = build(tmp_path, name="b.nc")
    assert check_files([same_a, same_b]).rules("E") == {"X01"}   # overlap


def test_x01_calendars_compare_by_mitgcm_mapping(tmp_path):
    a = _year_file(tmp_path, 2000, calendar="standard")
    b = _year_file(tmp_path, 2001, calendar="gregorian")
    r = check_files([a, b])
    assert r.findings == [], r.format_text()
    b = _year_file(tmp_path, 2001, calendar="noleap")
    r = check_files([a, b])
    assert r.rules("E") == {"X01"}
    assert any("noLeapYear" in f.message for f in r.errors)


def test_m06_file_named_2001_with_2000_records(tmp_path):
    p = build(tmp_path, name="runoff_2001.nc")
    r = check_files(p)
    assert r.rules("E") == {"M06"}
    assert all("year 2001" in f.message for f in r.errors)


# ---------------------------------------------------------------------------
# Correction round 2: X01 time offsets and fixed spacing, S08 scope and ASCII,
# S09, P02, R03 on packed lon/lat, month edges within tolerance, January start


def _daily_year(tmp_path, year, frac, name=None):
    """Daily ``runoff_<year>.nc`` with bounds [d, d+1) and time d + frac."""
    d = np.arange(DAYS_IN_YEAR[year], dtype=float)
    return build(tmp_path, dict(time_units="days since {0}-01-01".format(year),
                                time=d + frac, time_bnds=np.stack([d, d + 1], 1)),
                 name=name or "runoff_{0}.nc".format(year))


def test_x01_yearly_offset_uses_first_time_value(tmp_path):
    """MF1: contiguous bounds, but 2001 puts time at the start of each day."""
    files = [_daily_year(tmp_path, y, f) for y, f in ((2000, 0.5), (2001, 0.0), (2002, 0.5))]
    r = check_files(files)
    assert r.rules("E") == {"X01"}, r.format_text()
    msgs = [f.message for f in r.errors]
    assert any("runoff_2001.nc: first time is 0 s" in m and "share one start offset" in m
               for m in msgs), msgs
    assert not any("gap" in m or "overlap" in m for m in msgs)     # bounds are contiguous
    assert main(files) == 1


def test_x01_all_files_with_time_at_start_pass(tmp_path):
    """MF1: one common offset (time at the start of each day) is consistent."""
    files = [_daily_year(tmp_path, y, 0.0) for y in (2000, 2001, 2002)]
    r = check_files(files)
    assert r.findings == [], r.format_text()


def test_x01_fixed_spacing_across_files(tmp_path):
    """MF1: fixed sampling, contiguous bounds, spacing across the boundary 0.5 day."""
    d = np.arange(4, dtype=float)
    a = build(tmp_path, dict(time=d + 0.5, time_bnds=np.stack([d, d + 1], 1)), name="a.nc")
    b = build(tmp_path, dict(time_units="days since 2000-01-05", time=d + 0.0,
                             time_bnds=np.stack([d, d + 1], 1)), name="b.nc")
    r = check_files([a, b])
    assert r.rules("E") == {"X01"}, r.format_text()
    f, = r.errors
    assert "43200 s after the last time" in f.message and "mitgcm_time_period" in f.message
    good = build(tmp_path, dict(time_units="days since 2000-01-05", time=d + 0.5,
                                time_bnds=np.stack([d, d + 1], 1)), name="c.nc")
    assert check_files([a, good]).findings == []


@pytest.mark.parametrize("value", ["µmol kg-1", b"\xc2\xb5mol kg-1"], ids=["str", "bytes"])
def test_s08_non_ascii_model_read_attribute(tmp_path, value):
    """MF3: a model-read text attribute must be ASCII, whatever its stored type."""
    p = build(tmp_path, modifier=lambda ds: ds.variables["runoff_ptracer_dye"].setncattr(
        "units", value))
    r = check_files(p)
    assert r.rules() == {"S08"}, r.format_text()
    assert any("is not ASCII" in f.message and f.variable == "runoff_ptracer_dye"
               for f in r.errors)


def test_s08_ascii_is_checked_without_libnetcdf(tmp_path, monkeypatch):
    from MITgcmutils.runoff import check as C
    monkeypatch.setattr(C, "_libnetcdf", lambda: None)
    p = build(tmp_path, modifier=lambda ds: ds.variables["runoff_ptracer_dye"].setncattr(
        "units", b"\xc2\xb5mol kg-1"))
    r = check_files(p)
    assert r.rules("E") == {"S08"} and r.rules("W") == {"S08"}, r.format_text()


def test_s08_descriptive_mitgcm_attributes_may_be_utf8_ncstring(tmp_path):
    """MF3: mitgcm_grid_name/description are not model-read (schema 4.2)."""
    def fn(ds):
        ds.setncattr_string("mitgcm_grid_name", "lab_sea")
        ds.setncattr_string("mitgcm_grid_description", "cs32 cubed sphere, 2.8° cells")
    p = build(tmp_path, modifier=fn)
    r = check_files(p)
    assert r.findings == [], r.format_text()


@pytest.mark.parametrize("var, value, fires", [
    ("runoff_flux", "-999", True),
    ("runoff_flux", np.float64(-999.0), True),
    ("runoff_flux", np.float32(-999.0), False),
    ("target_fraction", "none", True),
    ("target_lon", "none", False),              # not model-read
])
def test_s09_missing_value_type(tmp_path, var, value, fires):
    """MF4: missing_value on a model-read variable is a number of its own type."""
    p = build(tmp_path, modifier=lambda ds: ds.variables[var].setncattr("missing_value", value))
    r = check_files(p)
    assert ("S09" in r.rules("E")) == fires, r.format_text()
    assert r.rules() <= {"S09"}, r.format_text()    # text is never used as a fill value
    if fires:
        assert r.errors[0].variable == var and main([p]) == 1


def _build_filtered(tmp_path, var, create, name):
    try:
        return build(tmp_path, dict(var_create={var: create}), name=name)
    except (ValueError, RuntimeError, TypeError) as e:   # plugin not in this netCDF
        pytest.skip("netCDF4 can't write {0}: {1}".format(create, e))


@pytest.mark.parametrize("var, create, fires", [
    ("runoff_flux", {"compression": "zstd", "complevel": 4}, True),
    ("runoff_flux", {"compression": "bzip2", "complevel": 4}, True),
    ("target_fraction", {"compression": "zstd"}, True),
    ("runoff_flux", {"compression": "zlib", "complevel": 4, "shuffle": True,
                     "fletcher32": True}, False),
    ("target_lon", {"compression": "zstd"}, False),   # not model-read
], ids=["flux-zstd", "flux-bzip2", "fraction-zstd", "flux-zlib-shuffle-fletcher32",
        "lon-zstd"])
def test_p02_filters(tmp_path, var, create, fires):
    p = _build_filtered(tmp_path, var, create, "runoff.nc")
    with netCDF4.Dataset(p) as ds:
        assert ds.variables[var].filters()[create["compression"]]
    r = check_files(p)
    assert r.rules() == ({"P02"} if fires else set()), r.format_text()
    if fires:
        f, = r.errors
        assert f.variable == var and create["compression"] in f.message
        assert main([p]) == 1


def test_p02_unreadable_series_is_reported_not_raised(tmp_path, monkeypatch):
    from MITgcmutils.runoff import check as C
    p = _build_filtered(tmp_path, "runoff_flux", {"compression": "zstd"}, "runoff.nc")

    real = C._stream_values

    def no_plugin(ctx, name, var, max_block_bytes):   # only the zstd variable fails
        if name == "runoff_flux":
            raise RuntimeError("NetCDF: Filter error: undefined filter encountered")
        return real(ctx, name, var, max_block_bytes)
    monkeypatch.setattr(C, "_stream_values", no_plugin)
    r = check_files(p)
    assert r.rules() == {"P02"}, r.format_text()
    assert any("could not be read" in f.message for f in r.errors)


@pytest.mark.parametrize("sampling", ["monthly", "yearly"])
@pytest.mark.parametrize("shift_days, ok", [(-1e-9, True), (1e-9, True), (-2e-8, False)])
def test_m05_period_edges_within_tolerance(tmp_path, sampling, shift_days, ok):
    """Richard A c4: edges 86.4 us early are the edges; 1.7 ms early is not."""
    if sampling == "monthly":
        spec = _monthly(MONTH_EDGES_2000)
    else:
        spec = dict(time=[183.0, 548.5], time_bnds=[[0, 366], [366, 731]],
                    time_sampling="yearly", time_period=None)
    spec = dict(spec, time=np.asarray(spec["time"]) + shift_days,
                time_bnds=np.asarray(spec["time_bnds"], dtype=float) + shift_days)
    r = check_files(build(tmp_path, spec))
    if ok:
        assert r.findings == [], r.format_text()
    else:
        assert r.rules("E") == {"M05"}, r.format_text()


def test_m05_monthly_climatology_must_start_in_january(tmp_path):
    assert check_files(build(tmp_path, _clim_360(1))).findings == []
    r = check_files(build(tmp_path, _clim_360(7), name="july.nc"))
    assert r.rules("E") == {"M05"}, r.format_text()
    f, = r.errors
    assert "must start in January" in f.message


# ---------------------------------------------------------------------------
# Grid checks (R01-R03) from MITgcm grid output


def test_grid_dir_clean(tmp_path, grid_dir):
    p = build(tmp_path)
    assert check_files(p, grid_dir=grid_dir).findings == []
    assert main([p, "--grid-dir", grid_dir, "--strict"]) == 0
    # cell 0 is land only below level 1: not a surface-land target
    p = build(tmp_path, dict(target_cell=[0, 70, 125, 233, 234]), name="c0.nc")
    assert "R01" not in check_files(p, grid_dir=grid_dir).rules()


def test_r01_land_cell(tmp_path, grid_dir):
    p = build(tmp_path, dict(target_cell=[69, 70, 125, 233, LAND_CELL]))
    r = check_files(p, grid_dir=grid_dir)
    assert r.rules("E") == {"R01"}, r.format_text()
    assert r.errors[0].source_id == "jakobshavn"
    assert "i={0}, j={1}".format(LAND_CELL % NX, LAND_CELL // NX) in r.errors[0].message
    assert main([p, "--grid-dir", grid_dir]) == 1


@pytest.mark.parametrize("stored_packed, fires", [(True, False), (False, True)],
                         ids=["packed-correct", "packed-attrs-on-unpacked-values"])
def test_r03_compares_unpacked_lon_lat(tmp_path, grid_dir, stored_packed, fires):
    """Richard A p05: target_lon/lat are not model-read and may be packed."""
    def fn(ds):
        for name in ("target_lon", "target_lat"):
            v = ds.variables[name]
            v.set_auto_maskandscale(False)
            true = np.asarray(v[:], dtype=np.float64)
            v.setncattr("scale_factor", np.float32(0.5))
            v.setncattr("add_offset", np.float32(10.0))
            if stored_packed:
                v[:] = ((true - 10.0) / 0.5).astype(v.dtype)
    p = build(tmp_path, modifier=fn)
    r = check_files(p, grid_dir=grid_dir)
    assert ("R03" in r.rules("W")) == fires, r.format_text()
    assert r.rules() <= {"R03"}, r.format_text()   # packing them is not S07


def test_float32_target_cell_area(tmp_path, grid_dir):
    """Schema 3.4: target_cell_area is double, float allowed."""
    p = build(tmp_path, dict(dtypes={"target_cell_area": "f4"}))
    with netCDF4.Dataset(p) as ds:
        assert ds.variables["target_cell_area"].dtype == np.float32
    assert check_files(p, grid_dir=grid_dir).findings == []


@pytest.mark.parametrize("rel, fires", [(2e-4, True), (5e-5, False)])
def test_r02_cell_area(tmp_path, grid_dir, rel, fires):
    rac = lab_sea_grid()[2].ravel()[EX_CELLS]
    p = build(tmp_path, dict(target_cell_area=rac * (1 + rel)))
    r = check_files(p, grid_dir=grid_dir)
    assert ("R02" in r.rules("E")) == fires, r.format_text()
    assert main([p, "--grid-dir", grid_dir]) == (1 if fires else 0)


def test_r03_lon_lat(tmp_path, grid_dir):
    xc, yc, _ = lab_sea_grid()
    p = build(tmp_path, dict(target_lon=xc.ravel()[EX_CELLS] + 0.01))
    r = check_files(p, grid_dir=grid_dir)
    assert r.rules() == {"R03"} and r.rules("W") == {"R03"}
    assert main([p, "--grid-dir", grid_dir]) == 0
    assert main([p, "--grid-dir", grid_dir, "--strict"]) == 1
    # longitudes written in [-180, 180) match XC in [0, 360)
    p = build(tmp_path, dict(target_lon=xc.ravel()[EX_CELLS] - 360.0), name="w.nc")
    assert check_files(p, grid_dir=grid_dir).findings == []


def test_grid_shape_mismatch_is_g01(tmp_path, grid_dir):
    p = build(tmp_path, dict(nx=40, ny=8))
    r = check_files(p, grid_dir=grid_dir)
    assert r.rules("E") == {"G01"}, r.format_text()


def test_global_hfacc_file(tmp_path):
    d = tmp_path / "g"
    d.mkdir()
    xc, yc, rac = lab_sea_grid()
    hf = np.ones(xc.shape)
    hf.ravel()[233] = 0.0
    for name, a in (("hFacC", hf), ("RAC", rac), ("XC", xc), ("YC", yc)):
        write_mds(str(d / name), a)
    r = check_files(build(tmp_path), grid_dir=str(d))
    assert r.rules() == {"R01"} and r.errors[0].source_id == "jakobshavn"


def test_missing_grid_file_is_io_error(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main([build(tmp_path), "--grid-dir", str(empty)]) == 2


# ---------------------------------------------------------------------------
# Streaming, CLI and JSON


def test_streaming_finds_error_in_last_block(tmp_path):
    n = 2000
    p = build(tmp_path, dict(time=np.arange(n) + 0.5), name="long.nc",
              modifier=setv("runoff_flux", (n - 1, 1), np.nan))
    r = check_files(p, max_block_bytes=1200)        # 100 records per block
    assert r.stats["blocks_read"]["{0}::runoff_flux".format(p)] == 20
    assert r.rules("E") == {"D02"}, r.format_text()
    f, = r.errors
    assert (f.record, f.time, f.source_id) == (n - 1, n - 0.5, "koksoak")
    assert "record {0}".format(n - 1) in f.message
    r = check_files(p)                               # default: one block
    assert r.stats["blocks_read"]["{0}::runoff_flux".format(p)] == 1
    assert r.rules("E") == {"D02"}


def test_json_output_parses(tmp_path):
    p = build(tmp_path, modifier=setv("runoff_flux", (0, 0), np.nan))
    out = tmp_path / "report.json"
    assert main([p, "--json", str(out)]) == 1
    data = json.loads(out.read_text())
    assert data["counts"]["E"] == 1 and data["files"] == [p]
    assert data["findings"][0]["rule"] == "D02"
    assert data["findings"][0]["source_id"] == "churchill_labrador"


def test_usage_and_io_errors_exit_2(tmp_path):
    assert main([]) == 2
    assert main([str(tmp_path / "missing.nc")]) == 2
    junk = tmp_path / "junk.nc"
    junk.write_text("not netcdf")
    assert main([str(junk)]) == 2


def _package_env():
    """Environment whose PYTHONPATH finds the in-repo MITgcmutils."""
    return dict(os.environ, PYTHONPATH=str(ROOT / "MITgcm" / "utils" / "python" / "MITgcmutils"))


def test_cli_module_runs_without_runtime_warning(example):
    """``python -m MITgcmutils.runoff.check`` must not trigger runpy's warning.

    If the package ``__init__`` imported ``check`` eagerly, runpy would find
    ``MITgcmutils.runoff.check`` in ``sys.modules`` before running it as
    ``__main__`` and emit a RuntimeWarning; ``-W error::RuntimeWarning`` turns
    that into a failure.
    """
    r = subprocess.run([sys.executable, "-W", "error::RuntimeWarning", "-m",
                        "MITgcmutils.runoff.check", example],
                       env=_package_env(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RuntimeWarning" not in r.stderr, r.stderr
    assert "0 error(s), 0 warning(s)" in r.stdout, r.stdout


def test_package_exports_are_lazy():
    """Importing the package loads only ``schema``; the exports load on first use."""
    code = "\n".join([
        "import sys",
        "import MITgcmutils.runoff as R",
        "assert 'MITgcmutils.runoff.check' not in sys.modules",
        "assert 'MITgcmutils.runoff.example' not in sys.modules",
        "from MITgcmutils.runoff import check_files, write_example, Finding, Report, schema",
        "from MITgcmutils.runoff.check import check_files as cf",
        "assert check_files is cf and R.Report.__module__ == 'MITgcmutils.runoff.check'",
        "ns = {}",
        "exec('from MITgcmutils.runoff import *', ns)",
        "assert set(R.__all__) <= set(ns) and set(R.__all__) <= set(dir(R))",
        "try:",
        "    R.no_such_name",
        "except AttributeError:",
        "    pass",
        "else:",
        "    raise SystemExit('no AttributeError')",
    ])
    r = subprocess.run([sys.executable, "-W", "error::RuntimeWarning", "-c", code],
                       env=_package_env(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# Tables-only mode (RUNOFF-009): time and time-series rules skipped, S10 says so

NO_SERIES = dict(time=None, time_bnds=None, runoff_flux=None, runoff_temperature=None,
                 runoff_salinity=None, ptracers={})


def test_tables_only_accepts_a_file_without_time_series(tmp_path, grid_dir):
    p = build(tmp_path, NO_SERIES)
    full = check_files(p)
    assert {"S03", "S04"} <= full.rules("E"), full.format_text()   # time dim, time, flux
    r = check_files(p, grid_dir=grid_dir, tables_only=True)
    assert r.errors == [] and r.warnings == [], r.format_text()
    s10 = [f for f in r.findings if f.rule == "S10"]
    assert len(s10) == 1 and s10[0].level == "I" and s10[0].file == p
    for skipped in schema.TABLES_ONLY_SKIPPED:
        assert skipped in s10[0].message
    assert r.stats["tables_only"] == list(schema.TABLES_ONLY_SKIPPED)
    assert main([p]) == 1
    assert main([p, "--tables-only", "--strict"]) == 0


def test_tables_only_still_checks_the_tables(tmp_path):
    """Table rules keep their meaning; only time and time-series rules are skipped."""
    p = build(tmp_path, dict(NO_SERIES, target_fraction=[0.7, 0.3, 1.0, 0.5, 0.49]))
    r = check_files(p, tables_only=True)
    assert r.rules("E") == {"T05"}, r.format_text()
    # A time-series fault in a full file is not looked at in tables-only mode.
    q = build(tmp_path, modifier=setv("runoff_flux", (2, 1), np.nan), name="full.nc")
    assert "D02" in check_files(q).rules("E")
    r = check_files(q, tables_only=True)
    assert r.errors == [] and r.rules() == {"S10"}, r.format_text()


def test_tables_only_several_files(tmp_path):
    """X01 still compares the tables; its time order and continuity checks are skipped."""
    a = build(tmp_path, NO_SERIES, name="a.nc")
    b = build(tmp_path, NO_SERIES, name="b.nc")
    r = check_files([a, b], tables_only=True)
    assert r.errors == [] and r.warnings == [], r.format_text()
    assert r.stats["tables_only"] == list(schema.TABLES_ONLY_SKIPPED
                                          + schema.TABLES_ONLY_SKIPPED_MULTI)
    # Two full files covering the same days overlap (X01), unless only tables are checked.
    fa, fb = build(tmp_path, name="fa.nc"), build(tmp_path, name="fb.nc")
    assert check_files([fa, fb]).rules("E") == {"X01"}
    r = check_files([fa, fb], tables_only=True)
    assert r.errors == [] and r.warnings == [], r.format_text()
    c = build(tmp_path, dict(NO_SERIES, target_fraction=[0.6, 0.4, 1.0, 0.5, 0.5]),
              name="c.nc")
    r = check_files([a, c], tables_only=True)
    assert r.rules("E") == {"X01"}, r.format_text()
    assert any("target_fraction" in f.message for f in r.errors)


# ---------------------------------------------------------------------------
# Every rule of schema section 9 is demonstrated above

DEMONSTRATED_ELSEWHERE = {"X01", "R01", "R02", "R03", "P02", "S10"}


def test_every_rule_has_a_demonstration():
    shown = {c.values[0] for c in E_CASES + W_CASES + I_CASES} | DEMONSTRATED_ELSEWHERE
    assert shown == set(schema.RULES)
