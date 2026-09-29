# Sparse runoff NetCDF schema, version 1.0

> **Status: proposed (RUNOFF-001), awaiting owner approval.** This is the file
> format that the MITgcm sparse-runoff reader (RUNOFF-004), the dense→sparse
> converter (RUNOFF-002) and the integrity checker read and write. The model
> behavior that uses the file is in [the model contract](model_contract.md).

A runoff file describes a set of **sources** (rivers, glaciers, ice-sheet basins,
groundwater outlets and so on). Each source feeds one or more ocean **target
cells** with a fixed **fraction** of its water. Each source has time series on
one shared **time** axis: a volume flux, and optionally temperature, salinity and
passive-tracer concentrations.

The file has three kinds of content:

| Part | Dimension | Read by MITgcm? | What it holds |
|---|---|---|---|
| Source table | `source` | only `source_id` | one row per source: id, names, notes, location, type |
| Alias table | `alias` | no | any number of extra names per source |
| Target table | `target` | yes | one row per (source, cell) pair: source index, cell index, fraction |
| Time series | `time` × `source` | yes | flux, temperature, salinity, tracers |

MITgcm reads only a small, fixed set of variables and attributes, marked
**model** below. Everything else is for people and tools, and you may add more
(see [Adding your own metadata](#5-adding-your-own-metadata)).

## 1. Conventions

- **Format:** NetCDF-4 (HDF5 storage), `NETCDF4` or `NETCDF4_CLASSIC`. You need
  NetCDF-4 for chunking, compression, files over 4 GB, and the variable-length
  strings used by the metadata variables.
- **Conventions attribute:** `Conventions = "CF-1.11, ACDD-1.3"`. Metadata follows
  [CF](https://cfconventions.org) and the
  [ACDD](https://wiki.esipfed.org/Attribute_Convention_for_Data_Discovery_1-3)
  global attributes. The schema version is in its own attribute,
  `mitgcm_runoff_schema_version`.
- **Indices are 0-based**, as in CF ragged arrays and numpy. The Fortran reader
  adds 1.
- **Units** are [UDUNITS](https://docs.unidata.ucar.edu/udunits/current/)
  strings. Each variable accepts only the spellings listed in
  [Allowed units](#6-allowed-units). MITgcm never converts units, so a value in
  another unit must be converted before it is written.
- **Reserved names:** schema variables start with `runoff_`, `source_`, `target_`
  or `alias_`, or are `time` / `time_bnds`. Model-control global attributes start
  with `mitgcm_`. A variable named `runoff_*` that the schema doesn't define is an
  error, because it is almost always a typo, like `runoff_temprature`.
- **Strings the model reads** (`source_id` only) are fixed-length `char` arrays,
  because the Fortran-77 NetCDF interface can't read variable-length strings. All
  other string variables may be either `char` arrays or variable-length `string`.

## 2. Dimensions

| Dimension | Size | Notes |
|---|---|---|
| `time` | number of records | Unlimited is recommended, so records can be appended. Slowest-varying dimension of every time series. |
| `source` | number of sources | |
| `target` | number of (source, cell) pairs | |
| `alias` | number of extra names | Optional. Omit it if there are no aliases. |
| `nv` | 2 | Bounds dimension for `time_bnds`. |
| `id_strlen` | maximum id length | Length of the `source_id` character dimension. Any name is allowed; `id_strlen` is recommended. At most 64. |

## 3. Variables

**Req.** is required (R), optional (O), or required under a condition. **Model**
marks what MITgcm reads.

### 3.1 Time

| Variable | Dims | Type | Req. | Model | Meaning |
|---|---|---|---|---|---|
| `time` | `(time)` | double | R | yes | The time each record represents, in CF form: `units = "<unit> since <date>"`, `calendar = "…"`, `axis = "T"`, `standard_name = "time"`, `bounds = "time_bnds"`. For averaged data this is normally the **midpoint** of the averaging interval, as in exf dense forcing. Linear interpolation runs between these times. |
| `time_bnds` | `(time, nv)` | double | R if more than one record | yes (hold-exact) | Start and end of the interval each record covers. Hold-exact mode applies each record over `[start, end)`. Same units and calendar as `time`. |

**Time rules:**

- `time` values are finite, strictly increasing and have no fill values.
- Bounds satisfy `start ≤ time ≤ end` and `start < end`. They are contiguous:
  each record's end equals the next record's start.
- `calendar` is one of the [allowed calendars](#63-calendars), and it must match
  the MITgcm `cal` package setting (checked by the model at init).

### 3.2 Source table (dimension `source`)

| Variable | Dims | Type | Req. | Model | Meaning |
|---|---|---|---|---|---|
| `source_id` | `(source, id_strlen)` | char | R | yes | Unique, stable identifier used in model error messages. ASCII letters, digits, `_`, `-` and `.`; starts with a letter or digit; no spaces; at most 64 characters. Ids must be unique, and unique ignoring case. |
| `source_name` | `(source)` | string | O | no | Primary human-readable name, e.g. `"Jakobshavn Isbræ"`. UTF-8. |
| `source_type` | `(source)` | string | O | no | Kind of source. Recommended values: `river`, `glacier`, `ice_sheet_basin`, `iceberg_melt`, `groundwater`, `other`. Other values give a warning, not an error. |
| `source_lon` | `(source)` | float/double | O | no | Longitude of the mouth or terminus, `units = "degrees_east"`. |
| `source_lat` | `(source)` | float/double | O | no | Latitude of the mouth or terminus, `units = "degrees_north"`. |
| `source_notes` | `(source)` | string | O | no | Free-text notes: provenance, caveats, processing history. May contain newlines. |
| `source_reference` | `(source)` | string | O | no | Citation, DOI or URL for this source's data. |

### 3.3 Alias table (dimension `alias`, optional)

Rivers and glaciers often have several names: local-language names, historical
names and catalogue ids (RGI, GLIMS, GRDC, GNIS…). Each row of the alias table is
one extra name for one source. A source can have any number of aliases.

| Variable | Dims | Type | Req. | Model | Meaning |
|---|---|---|---|---|---|
| `alias_source` | `(alias)` | int | R if `alias` exists | no | 0-based index into `source`. Attribute `instance_dimension = "source"`. |
| `alias_name` | `(alias)` | string | R if `alias` exists | no | The alternative name or catalogue id, e.g. `"Sermeq Kujalleq"`, `"RGI60-05.01390"`. |
| `alias_scheme` | `(alias)` | string | O | no | Naming system or authority the alias comes from, e.g. `"Greenlandic"`, `"RGI 6.0"`, `"GRDC"`, `"historical"`. |

### 3.4 Target table (dimension `target`)

The target table is a CF *indexed ragged array*: each row belongs to one source.
Rows may appear in any order. Sorting by source and then cell is recommended.

| Variable | Dims | Type | Req. | Model | Meaning |
|---|---|---|---|---|---|
| `target_source` | `(target)` | int | R | yes | 0-based index into `source`. Attribute `instance_dimension = "source"`. |
| `target_cell` | `(target)` | int (int32 recommended; int64 allowed) | R | yes | 0-based global cell index, `cell = i + mitgcm_grid_nx · j`. `(i, j)` are the 0-based positions in the global 2D array that MITgcm reads from a dense `runoffFile` on this grid, with `i` varying fastest (Fortran order). For exch2 cubed-sphere and LLC grids this is the global I/O layout, e.g. 192 × 32 for cs32 and 90 × 1170 for LLC90. |
| `target_fraction` | `(target)` | double (float allowed) | R | yes | Share of the source's flux sent to this cell, `units = "1"`. Each value is in `[0, 1]`. Each source's fractions sum to 1 within 1e-6. |
| `target_level` | `(target)` | int | O | yes | Reserved for 3D runoff: the 1-based model level `k`. Schema 1.0 allows only 1. If absent, every target is level 1. |
| `target_cell_area` | `(target)` | double | O | yes | Horizontal area `rA` of the cell on the grid the file was built for, in m². If present, the model compares it with its own `rA` (relative tolerance 1e-4) to catch a file built for a different grid. |
| `target_lon` | `(target)` | float/double | O | no | Cell-center longitude, `degrees_east`. For people and plots. |
| `target_lat` | `(target)` | float/double | O | no | Cell-center latitude, `degrees_north`. |

**Target rules:** each `(source, cell, level)` triple appears at most once, so merge
duplicates before writing. Different sources may share a cell. The model adds
their volumes and flux-weights their temperature, salinity and tracers.

### 3.5 Time series (dims `(time, source)`)

All time series have dimensions exactly `(time, source)`, in that order, so each
record is one contiguous hyperslab. Stored as float (32-bit) or double.

| Variable | Req. | Model | Units | Missing values |
|---|---|---|---|---|
| `runoff_flux` | R | yes | volume flux, [m³ s⁻¹](#61-physical-variables) | **Not allowed.** Any fill value, NaN or Inf is an error, and the model stops. |
| `runoff_temperature` | O | yes | [°C](#61-physical-variables) | Allowed: the source enters at the surface water temperature, the same as when the variable is absent. |
| `runoff_salinity` | O | yes | [model salinity units](#61-physical-variables) | Not allowed. If the variable is absent, salinity is 0. |
| `runoff_ptracer_<NAME>` | O | yes | any non-empty string, which must equal the ptracer's own concentration units | Not allowed. |

- **Passive tracers:** `<NAME>` must equal a `PTRACERS_names` entry in
  `data.ptracers` (letters, digits and `_`). Any number is allowed. A tracer with
  no matching ptracer is fatal in the model. Its concentration is per unit volume
  of runoff water.
- **Recommended variable attributes:** `long_name`, `units`, `comment`. `runoff_flux`
  may carry `standard_name = "water_volume_transport_into_sea_water_from_rivers"`
  when every source is a river.
- **Negative flux** is allowed by the model but flagged by the checker as a
  warning.

## 4. Global attributes

### 4.1 Read by MITgcm

| Attribute | Type | Req. | Meaning |
|---|---|---|---|
| `mitgcm_runoff_schema_version` | string | R | `"1.0"`. The model refuses a major version it doesn't know. |
| `mitgcm_grid_nx` | int | R | Width of the global 2D layout used by `target_cell`. |
| `mitgcm_grid_ny` | int | R | Height of that layout. The model stops if `(nx, ny)` differs from its own global layout. |
| `mitgcm_time_sampling` | string | R | `constant` (one record), `fixed` (a constant period, e.g. hourly or daily), `monthly` (calendar months) or `yearly` (calendar years). |
| `mitgcm_time_period` | double | R if `fixed` | Record spacing in seconds, e.g. 3600 or 86400. |
| `mitgcm_time_repeat` | string | O | `none` (default) or `annual`: the records are a climatology that repeats every model year. |

`data.exf` settings override every timing attribute above. Exact parameter names
are defined in RUNOFF-005.

### 4.2 Grid description (recommended, not read)

`mitgcm_grid_name` (e.g. `"global_ocean.cs32x15"`, `"LLC270"`) and
`mitgcm_grid_description` (free text: how the global layout is arranged, where
the grid files came from).

### 4.3 Discovery and provenance (recommended ACDD / CF)

`title`, `summary`, `institution`, `source`, `history`, `references`, `comment`,
`creator_name`, `creator_email`, `creator_url`, `contributor_name`,
`contributor_role`, `project`, `license`, `date_created`, `date_modified`,
`product_version`, `keywords`, `time_coverage_start`, `time_coverage_end`,
`geospatial_lat_min`, `geospatial_lat_max`, `geospatial_lon_min`,
`geospatial_lon_max`. The checker reports any that are missing as information,
not as errors.

## 5. Adding your own metadata

The model ignores anything it doesn't read, so you can add:

- **Global attributes:** any name that doesn't start with `mitgcm_`.
- **Per-source variables** on dimension `(source)`, e.g. `source_drainage_area`
  (m²), `source_basin_id` or `source_dataset`. **Per-target variables** on
  `(target)`. Use the `source_` / `target_` prefix so their meaning is clear.
- **Additional time series** that aren't model inputs, e.g. a discharge
  uncertainty. These must **not** start with `runoff_`. Use a name like
  `flux_uncertainty(time, source)`.
- **Variable attributes** on any variable, including schema ones: `comment`,
  `source`, `references` and so on.

Give each added variable `long_name` and, where meaningful, `units`.

## 6. Allowed units

The checker compares units after trimming surrounding spaces. Spellings are
case-sensitive except `celsius` / `Celsius`.

### 6.1 Physical variables

| Variable | Canonical | Also accepted | Notes |
|---|---|---|---|
| `runoff_flux` | `m3 s-1` | `m3/s`, `m^3/s`, `m3.s-1`, `m^3 s^-1`, `m3 s^-1` | Volume flux only. Mass fluxes (`kg s-1`, `Gt yr-1`) and `Sv` or `km3 yr-1` are rejected. Convert them first. |
| `runoff_temperature` | `degC` | `degree_Celsius`, `degrees_Celsius`, `degree_C`, `degrees_C`, `celsius`, `Celsius` | Kelvin is rejected. |
| `runoff_salinity` | `g kg-1` | `g/kg`, `1e-3`, `0.001`, `psu`, `PSU`, `PSS-78`, `1` | The value is used as-is in the model's salinity units (practical or absolute, depending on the equation of state). The unit records which one. |
| `runoff_ptracer_<NAME>` | — | any non-empty string | Must match the ptracer's own units. Not checked. |

### 6.2 Coordinates and table variables

| Variable | Allowed units |
|---|---|
| `time`, `time_bnds` | `<days\|hours\|minutes\|seconds> since <YYYY-MM-DD>[ hh:mm[:ss]][Z]`; `T` as the date/time separator is also accepted |
| `target_fraction` | `1` |
| `target_cell_area` | `m2`, `m^2` |
| `*_lon` | `degrees_east`, `degree_east`, `degree_E`, `degrees_E` |
| `*_lat` | `degrees_north`, `degree_north`, `degree_N`, `degrees_N` |
| `target_source`, `target_cell`, `target_level`, `alias_source` | no `units` attribute (they are indices) |

### 6.3 Calendars

| CF `calendar` | MITgcm `cal` package `TheCalendar` |
|---|---|
| `standard`, `gregorian`, `proleptic_gregorian` | `gregorian` |
| `noleap`, `365_day` | `noLeapYear` |
| `360_day` | `model` |

A missing `calendar` attribute means `standard`, as in CF. The checker warns so
that the calendar is written explicitly.

## 7. Time sampling, repeats and yearly files

| `mitgcm_time_sampling` | Records | Checker verifies |
|---|---|---|
| `constant` | 1 | exactly one record |
| `fixed` | any | spacing of `time` equals `mitgcm_time_period` everywhere |
| `monthly` | any | consecutive calendar months, each record's bounds are exactly its month |
| `yearly` | any | consecutive calendar years, bounds are exactly the year |

- **Climatology** (`mitgcm_time_repeat = "annual"`): the records cover exactly
  one year (e.g. 12 monthly or 365 daily records). The year number in `time` is
  nominal.
- **Yearly files:** a name ending `_YYYY.nc` holds the records of model year
  `YYYY`, following exf `useExfYearlyFields`. Every record's bounds lie within
  that year. All yearly files of one data set have identical source, alias and
  target tables and the same variables. Only the records differ.

## 8. Storage, chunking and compression

The main use case is daily records for 50 years at 10⁵–10⁶ sources: tens of GB
per variable in float32. The model reads two bracketing records of every
time series per update, so:

- Time is the first (slowest) dimension of every time series.
- Chunk time series with **1 record per chunk** along `time` and a large chunk
  along `source`. The whole source dimension works when it fits in about 4 MB
  (1 million float32 values); otherwise use equal pieces of about that size.
  RUNOFF-002 settles the final recommendation by a measured read benchmark. The
  checker warns when a chunk covers more than one record, because then reading
  one record decompresses several.
- Compression (`zlib`, level 1–4, with `shuffle`) is allowed and recommended for
  large files.
- The static tables (`source`, `target`, `alias`) are small (about 16 MB at 10⁶
  targets) and are read once at init.

## 9. Integrity rules and the checker

`check_runoff_file` (package `MITgcmutils.runoff`, see RUNOFF-001) validates one
file, or a set of yearly files together:

```sh
python -m MITgcmutils.runoff.check runoff_2000.nc runoff_2001.nc
python -m MITgcmutils.runoff.check runoff.nc --grid-dir run/ --json report.json
```

It exits 0 when there are no errors, 1 when there are errors, and 2 for a usage
or I/O problem. `--strict` also fails on warnings. With `--grid-dir` it reads the
MITgcm grid output (`hFacC`, `RAC`, `XC`, `YC`) and runs the grid checks as well.
It reads time series one block of records at a time, so memory stays bounded for
very large files.

Each finding has a rule id. **E** is an error (the model would stop or
misbehave), **W** a warning (suspicious but usable), **I** information.

| Rule | Level | Check |
|---|---|---|
| `S01` | E | File is NetCDF-4 (`NETCDF4` or `NETCDF4_CLASSIC`). |
| `S02` | E | `mitgcm_runoff_schema_version` is present and supported. |
| `S03` | E | Required dimensions exist; `nv` is 2; the id string dimension is ≤ 64. |
| `S04` | E | Required variables exist with the documented dimensions and type class. |
| `S05` | E | No undefined `runoff_*` variable, and no undefined `mitgcm_*` global attribute. |
| `S06` | I | Recommended ACDD / CF global attributes are missing. |
| `G01` | E | `mitgcm_grid_nx` and `mitgcm_grid_ny` are positive integers. |
| `I01` | E | `source_id` values are non-empty, allowed characters, ≤ 64 characters. |
| `I02` | E | `source_id` values are unique. |
| `I03` | W | Two ids differ only in letter case. |
| `I04` | W | `source_type` is not a recommended value. |
| `A01` | E | `alias_source` indices are in `[0, n_source)`; `alias_name` is non-empty. |
| `A02` | W | A source has the same alias twice. |
| `T01` | E | `target_source` indices are in `[0, n_source)`. |
| `T02` | E | `target_cell` is in `[0, nx·ny)`. |
| `T03` | E | No duplicate `(source, cell, level)` triple. |
| `T04` | E | Fractions are finite and in `[0, 1]`. |
| `T05` | E | Each source's fractions sum to 1 within 1e-6 (every source therefore has at least one target). |
| `T06` | W | A fraction is exactly 0. |
| `T07` | E | `target_level`, if present, is 1 everywhere (schema 1.0). |
| `T08` | I | Targets are not sorted by source and cell. |
| `M01` | E | `time` units and `calendar` are allowed. |
| `M02` | W | `calendar` attribute is missing. |
| `M03` | E | `time` is finite and strictly increasing. |
| `M04` | E | `time_bnds` is present when there is more than one record; bounds contain their time, have positive length and are contiguous. |
| `M05` | E | `mitgcm_time_sampling`, `mitgcm_time_period` and `mitgcm_time_repeat` are valid and consistent with `time` and `time_bnds` (§7). |
| `M06` | E | A `_YYYY` file's records all lie within year `YYYY`. |
| `D01` | E | Each time series has dims `(time, source)`, a float type and allowed `units`. |
| `D02` | E | `runoff_flux` has no fill, NaN or Inf values. |
| `D03` | W | `runoff_flux` is negative somewhere. |
| `D04` | W | `runoff_temperature` is outside `[-2.5, 40]` °C. |
| `D05` | E | `runoff_salinity` has missing or negative values. |
| `D06` | W | `runoff_salinity` is above 45. |
| `D07` | E | A `runoff_ptracer_<NAME>` has an invalid name, empty `units`, or missing values. |
| `D08` | W | A ptracer concentration is negative. |
| `U01` | E | A `units` attribute is not in the allowed list (§6). |
| `P01` | W | A time-series chunk spans more than one record along `time`. |
| `X01` | E | Across several files: identical source, alias and target tables, grid attributes and variable set; records in time order with no overlap. |
| `R01` | E | (`--grid-dir`) A target cell is on land (`hFacC` = 0 at level 1). |
| `R02` | E | (`--grid-dir`) `target_cell_area` differs from `RAC` by more than 1e-4 relative. |
| `R03` | W | (`--grid-dir`) `target_lon` / `target_lat` differ from `XC` / `YC` by more than 1e-3 degrees. |

## 10. Example header

A tiny example with 3 sources, 5 targets, 2 aliases and 4 daily records is
generated by `MITgcmutils.runoff.example.write_example()`.

<!-- ncdump -h of the generated example is inserted here when the checker lands. -->

## 11. Writing a file with xarray

```python
import numpy as np, xarray as xr

ds = xr.Dataset(
    {
        "source_id": ("source", np.array(["amazon", "jakobshavn"])),
        "source_name": ("source", np.array(["Amazon", "Jakobshavn Isbræ"], dtype=object)),
        "target_source": ("target", np.array([0, 0, 1], dtype="i4")),
        "target_cell": ("target", np.array([1203, 1204, 5711], dtype="i4")),
        "target_fraction": ("target", np.array([0.6, 0.4, 1.0])),
        "runoff_flux": (("time", "source"), flux.astype("f4")),  # m3 s-1
        # time and time_bnds as datetime64: xarray writes CF units/calendar
    },
    attrs={"mitgcm_runoff_schema_version": "1.0", "mitgcm_grid_nx": 192,
           "mitgcm_grid_ny": 32, "mitgcm_time_sampling": "fixed",
           "mitgcm_time_period": 86400.0},
)
ds["source_id"].encoding.update(dtype="S1", char_dim_name="id_strlen")  # char array for Fortran
ds["runoff_flux"].encoding.update(chunksizes=(1, ds.sizes["source"]), zlib=True, complevel=2)
ds.to_netcdf("runoff.nc", format="NETCDF4", unlimited_dims=["time"])
```

Run the checker on every file you write.

## 12. Versioning

`mitgcm_runoff_schema_version` is `MAJOR.MINOR`. A minor version only adds
content; a reader accepts any minor version of its own major version, and stops
with a clear error on content it can't honor. A major version changes the meaning
of existing content, and a reader refuses a major version it doesn't know.

3D runoff (`target_level` other than 1) is planned as version 1.1. A 1.0 reader
already reads `target_level` and stops on any value other than 1, so it never
silently puts subsurface runoff at the surface.
