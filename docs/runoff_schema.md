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
- **No packing.** Variables the model reads (`time`, `time_bnds`, `source_id`,
  `target_*` and `runoff_*`) must not carry `scale_factor` or `add_offset`. The
  Fortran reader reads stored values directly and does not unpack them.
- **Text attributes the model reads** are `char` (NC_CHAR) attributes, not
  `string` (NC_STRING) ones, because `NF_GET_ATT_TEXT` can't read NC_STRING. They
  are the `mitgcm_*` text attributes, `time:units`, `time:calendar`, and the
  `units` of every `runoff_*` variable. netCDF4-python and xarray write Python
  `str` attributes as `char` by default.
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
| `time` | `(time)` | double | R | yes | The time each record represents, in CF form: `units = "<unit> since <date>"`, `calendar = "…"`, `axis = "T"`, `standard_name = "time"`, `bounds = "time_bnds"`. For averaged data this is normally the **midpoint** of the averaging interval, as in exf dense forcing. Linear interpolation runs between these times. For `monthly` and `yearly` sampling, `time` must be the midpoint of its bounds, because exf interpolates between calendar-month (or year) midpoints and ignores the file's times (§7). |
| `time_bnds` | `(time, nv)` | double | R if more than one record | yes (hold-exact) | Start and end of the interval each record covers. Hold-exact mode applies each record over `[start, end)`. Same units and calendar as `time`. |

**Time rules:**

- `time` values are finite, strictly increasing and have no fill values.
- Bounds satisfy `start ≤ time ≤ end` and `start < end`. They are contiguous:
  each record's end equals the next record's start.
- `calendar` is one of the [allowed calendars](#63-calendars), matched ignoring
  letter case as in CF, and it must match
  the MITgcm `cal` package setting (checked by the model at init).

### 3.2 Source table (dimension `source`)

| Variable | Dims | Type | Req. | Model | Meaning |
|---|---|---|---|---|---|
| `source_id` | `(source, id_strlen)` | char | R | yes | Unique, stable identifier used in model error messages. ASCII letters, digits, `_`, `-` and `.`; starts with a letter or digit; no spaces; at most 64 characters. Trailing NUL or blank padding in the char array is not part of the id. Ids must be unique, and unique ignoring case. |
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
| `source_lon`, `target_lon` | `degrees_east`, `degree_east`, `degree_E`, `degrees_E` |
| `source_lat`, `target_lat` | `degrees_north`, `degree_north`, `degree_N`, `degrees_N` |
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
| `monthly` | any | consecutive calendar months, each record's bounds are exactly its month, and `time` is the midpoint of its bounds |
| `yearly` | any | consecutive calendar years, bounds are exactly the year, and `time` is the midpoint of its bounds |

- **Time tolerance:** "equal" for times in this section and in §3.1 (contiguous
  bounds, fixed spacing, month and year edges, yearly-file limits) means within
  1e-3 s.
- **Climatology** (`mitgcm_time_repeat = "annual"`): `time_bnds` is required, even
  for a single record, and the records cover exactly
  one year (e.g. 12 monthly or 365 daily records). The year number in `time` is
  nominal.
- **Checking several files (`X01`):** files are compared in the order given, so
  pass them in time order. Their calendars must map to the same MITgcm calendar
  (§6.3). "Identical tables" means every variable without a `time` dimension,
  including ones you added.
- **Yearly files:** a name ending `_YYYY.nc` holds the records of model year
  `YYYY`, following exf `useExfYearlyFields`. Every record's bounds lie within
  that year. All yearly files of one data set have identical source, alias and
  target tables and the same variables. Only the records differ.
- **Yearly files form one continuous series.** exf uses a single start offset
  for every year, so each file's first record must start at the same offset
  from 1 January of its year, and each file's first bound must equal the
  previous file's last bound. A gap or a shifted file would silently shift
  every record.

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

`check_files` (module `MITgcmutils.runoff.check`, also a command-line tool) validates one
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
| `S03` | E | Required dimensions exist; `time`, `source` and `target` are non-empty; `nv` is 2; the id string dimension is ≤ 64. |
| `S04` | E | Required variables exist, and every schema variable present has its documented dimensions and type class. `time` and `time_bnds` must be double. |
| `S05` | E | No undefined `runoff_*` variable, and no undefined `mitgcm_*` global attribute. |
| `S06` | I | Recommended ACDD / CF global attributes are missing. |
| `S07` | E | A model-read variable carries `scale_factor` or `add_offset`. |
| `S08` | E | A model-read text attribute (§1) is NC_STRING instead of `char`. |
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
| `D04` | W | `runoff_temperature` is outside `[-2.5, 40]` °C (fill and NaN values excluded). |
| `D05` | E | `runoff_salinity` has missing or negative values. |
| `D06` | W | `runoff_salinity` is above 45. |
| `D07` | E | A `runoff_ptracer_<NAME>` has an invalid name, empty `units`, or missing values. |
| `D08` | W | A ptracer concentration is negative. |
| `D09` | E | `runoff_temperature` contains ±Inf, or its `_FillValue` or `missing_value` is ±Inf. Inf is never a missing-value marker. |
| `U01` | E | A schema variable listed in §6 has a missing or disallowed `units` attribute. Index variables must not have one. |
| `P01` | W | A time-series chunk spans more than one record along `time`. |
| `X01` | E | Across several files: identical source, alias and target tables, grid attributes and variable set; records in time order, with each file's first bound equal to the previous file's last bound; yearly files share one within-year start offset. |
| `R01` | E | (`--grid-dir`) A target cell is on land (`hFacC` = 0 at level 1). |
| `R02` | E | (`--grid-dir`) `target_cell_area` differs from `RAC` by more than 1e-4 relative. |
| `R03` | W | (`--grid-dir`) `target_lon` / `target_lat` differ from `XC` / `YC` by more than 1e-3 degrees. |

## 10. Example header

A tiny example with 3 sources, 5 targets, 2 aliases and 4 daily records is
generated by `MITgcmutils.runoff.example.write_example()`.

```text
netcdf runoff_example {
dimensions:
	time = UNLIMITED ; // (4 currently)
	source = 3 ;
	target = 5 ;
	alias = 2 ;
	nv = 2 ;
	id_strlen = 18 ;
variables:
	double time(time) ;
		time:long_name = "time" ;
		time:standard_name = "time" ;
		time:axis = "T" ;
		time:units = "days since 2000-01-01 00:00:00" ;
		time:calendar = "standard" ;
		time:bounds = "time_bnds" ;
	double time_bnds(time, nv) ;
		time_bnds:long_name = "start and end of the interval each record covers" ;
	char source_id(source, id_strlen) ;
		source_id:long_name = "source identifier" ;
		source_id:cf_role = "timeseries_id" ;
	string source_name(source) ;
		source_name:long_name = "primary name of the source" ;
	string source_type(source) ;
		source_type:long_name = "kind of source" ;
		source_type:comment = "river, glacier, ice_sheet_basin, iceberg_melt, groundwater or other" ;
	double source_lon(source) ;
		source_lon:long_name = "longitude of the mouth or terminus" ;
		source_lon:standard_name = "longitude" ;
		source_lon:units = "degrees_east" ;
	double source_lat(source) ;
		source_lat:long_name = "latitude of the mouth or terminus" ;
		source_lat:standard_name = "latitude" ;
		source_lat:units = "degrees_north" ;
	string source_notes(source) ;
		source_notes:long_name = "notes on provenance and processing" ;
	string source_reference(source) ;
		source_reference:long_name = "citation, DOI or URL of the source data" ;
	int alias_source(alias) ;
		alias_source:long_name = "index of the source this alias names" ;
		alias_source:instance_dimension = "source" ;
	string alias_name(alias) ;
		alias_name:long_name = "alternative name or catalogue id" ;
	string alias_scheme(alias) ;
		alias_scheme:long_name = "naming system or authority of the alias" ;
	int target_source(target) ;
		target_source:long_name = "index of the source feeding this target" ;
		target_source:instance_dimension = "source" ;
	int target_cell(target) ;
		target_cell:long_name = "0-based global cell index" ;
		target_cell:comment = "cell = i + mitgcm_grid_nx * j, 0-based (i, j) in the global 2D layout of a dense runoffFile" ;
	double target_fraction(target) ;
		target_fraction:long_name = "share of the source flux sent to this cell" ;
		target_fraction:units = "1" ;
	int target_level(target) ;
		target_level:long_name = "1-based model level k (schema 1.0: always 1)" ;
	double target_cell_area(target) ;
		target_cell_area:long_name = "horizontal cell area rA" ;
		target_cell_area:units = "m2" ;
	double target_lon(target) ;
		target_lon:long_name = "cell-center longitude" ;
		target_lon:standard_name = "longitude" ;
		target_lon:units = "degrees_east" ;
	double target_lat(target) ;
		target_lat:long_name = "cell-center latitude" ;
		target_lat:standard_name = "latitude" ;
		target_lat:units = "degrees_north" ;
	float runoff_flux(time, source) ;
		runoff_flux:long_name = "runoff volume flux of the source" ;
		runoff_flux:units = "m3 s-1" ;
		runoff_flux:comment = "split among targets by target_fraction" ;
	float runoff_temperature(time, source) ;
		runoff_temperature:_FillValue = 9.96921e+36f ;
		runoff_temperature:long_name = "runoff temperature" ;
		runoff_temperature:units = "degC" ;
		runoff_temperature:comment = "fill value: enters at the surface water temperature" ;
	float runoff_salinity(time, source) ;
		runoff_salinity:long_name = "runoff salinity" ;
		runoff_salinity:units = "g kg-1" ;
	float runoff_ptracer_dye(time, source) ;
		runoff_ptracer_dye:long_name = "concentration of ptracer dye in runoff" ;
		runoff_ptracer_dye:units = "mol m-3" ;

// global attributes:
		:Conventions = "CF-1.11, ACDD-1.3" ;
		:mitgcm_runoff_schema_version = "1.0" ;
		:mitgcm_grid_nx = 20 ;
		:mitgcm_grid_ny = 16 ;
		:mitgcm_grid_name = "lab_sea" ;
		:mitgcm_grid_description = "lat-lon 2-degree grid, 20 x 16 cells from 280E, 46N; cell = i + 20*j (0-based)" ;
		:mitgcm_time_sampling = "fixed" ;
		:mitgcm_time_period = 86400. ;
		:mitgcm_time_repeat = "none" ;
		:title = "Example sparse runoff file for the lab_sea layout" ;
		:summary = "Three synthetic sources (two rivers, one glacier) feeding five ocean cells, four daily records." ;
		:institution = "MITgcm" ;
		:source = "MITgcmutils.runoff.example.write_example" ;
		:history = "created by MITgcmutils.runoff.example.write_example" ;
		:references = "docs/runoff_schema.md (sparse runoff schema 1.0)" ;
		:comment = "Synthetic values for testing and documentation only." ;
		:creator_name = "MITgcm developers" ;
		:creator_email = "mitgcm-support@mitgcm.org" ;
		:creator_url = "https://mitgcm.org" ;
		:contributor_name = "MITgcm developers" ;
		:contributor_role = "author" ;
		:project = "MITgcm sparse runoff" ;
		:license = "MIT" ;
		:date_created = "2026-09-29T00:00:00Z" ;
		:date_modified = "2026-09-29T00:00:00Z" ;
		:product_version = "1.0" ;
		:keywords = "runoff, river discharge, glacier discharge, MITgcm" ;
		:time_coverage_start = "2000-01-01T00:00:00Z" ;
		:time_coverage_end = "2000-01-05T00:00:00Z" ;
		:geospatial_lat_min = 53. ;
		:geospatial_lat_max = 69. ;
		:geospatial_lon_min = 291. ;
		:geospatial_lon_max = 309. ;
}
```

## 11. Writing a file with xarray

This complete recipe writes a minimal valid file; the test suite runs this
exact code block and checks its output. Add the optional variables and
attributes you need.

```python
import numpy as np
import xarray as xr

# Four daily records for two sources on the cs32 layout (192 x 32).
nt = 4
start = np.datetime64("2000-01-01")
t0 = start + np.arange(nt) * np.timedelta64(1, "D")           # interval starts
bnds = np.stack([t0, t0 + np.timedelta64(1, "D")], axis=1)     # [start, end)
time = t0 + np.timedelta64(12, "h")                            # midpoints
flux = np.array([[1200.0, 35.0]] * nt, dtype="f4")             # m3 s-1

ds = xr.Dataset(
    {
        "time_bnds": (("time", "nv"), bnds),
        "source_id": ("source", np.array(["amazon", "jakobshavn"])),
        "source_name": ("source", np.array(["Amazon", "Jakobshavn Isbræ"], dtype=object)),
        "target_source": ("target", np.array([0, 0, 1], dtype="i4")),
        "target_cell": ("target", np.array([1203, 1204, 5711], dtype="i4")),
        "target_fraction": ("target", np.array([0.6, 0.4, 1.0]), {"units": "1"}),
        "runoff_flux": (("time", "source"), flux, {"units": "m3 s-1"}),
    },
    coords={"time": ("time", time, {"bounds": "time_bnds", "axis": "T",
                                    "standard_name": "time"})},
    attrs={"Conventions": "CF-1.11, ACDD-1.3",
           "mitgcm_runoff_schema_version": "1.0",
           "mitgcm_grid_nx": np.int32(192), "mitgcm_grid_ny": np.int32(32),
           "mitgcm_time_sampling": "fixed", "mitgcm_time_period": 86400.0},
)

# time and time_bnds: double, with the same units and calendar
cf_time = {"units": "days since 2000-01-01 00:00:00", "calendar": "standard",
           "dtype": "float64"}
ds["time"].encoding.update(cf_time)
ds["time_bnds"].encoding.update(cf_time)
# source_id as a char array, which the Fortran-77 NetCDF API can read
ds["source_id"].encoding.update(dtype="S1", char_dim_name="id_strlen")
# one record per chunk; no fill value on the flux (missing flux is an error)
ds["runoff_flux"].encoding.update(chunksizes=(1, ds.sizes["source"]),
                                  zlib=True, complevel=2, _FillValue=None)
for name in ("target_fraction", "time", "time_bnds"):
    ds[name].encoding["_FillValue"] = None
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
