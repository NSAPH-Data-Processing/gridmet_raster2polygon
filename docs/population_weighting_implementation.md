# Population Weighting: Implementation Reference

This document describes the technical implementation of population-weighted aggregation in `gridmet_raster2polygon`. For scientific background, mathematical formulation, and citations, see [population_weighting_method.md](population_weighting_method.md).

---

## Architecture Overview

Population weighting is applied at Stage 2 of the pipeline (aggregation), and is transparent to all downstream stages:

```
Stage 1: download_gridmet.py       — raw NetCDF files
Stage 2: aggregate_gridmet.py      — raster → polygon (POPULATION WEIGHTING HERE)
Stage 3: format_gridmet.py         — join variables into daily dataset
Stage 4: get_yearly.py             — annual averages
Stage 5: seasonal_vars.py          — seasonal averages
```

Stages 3–5 process weighted and unweighted outputs identically; the weighted mean is stored as a standard column value in the intermediate Parquet file.

---

## File Changes

### New Files

| File | Purpose |
|------|---------|
| `src/download_population.py` | Downloads GPWv4 population GeoTIFF from Harvard Dataverse; resolves nearest available census year; caches raw zip to avoid re-download |
| `conf/population.yaml` | Configuration for population data sources, file mappings, and weighting toggle |
| `docs/population_weighting_method.md` | Scientific background, mathematical formulation, citations, and usage guide |

### Modified Files

| File | Change |
|------|--------|
| `conf/config.yaml` | Added `population` to Hydra defaults list |
| `utils/faster_zonal_stats.py` | Added `compute_zonal_stats()` with optional weighted mean |
| `src/aggregate_gridmet.py` | Added `align_population_to_gridmet()`, `load_population_weights()`, and integrated weighting into main loop |
| `Snakefile` | Added `download_population` rule |
| `README.md` | Added Population Weighting section with scientific context |

---

## Key Functions

### `align_population_to_gridmet()` — `src/aggregate_gridmet.py`

Reads the population GeoTIFF and reprojects it to exactly match the target gridMET grid (shape + affine transform). Uses nearest-neighbor resampling to preserve count integrity (see [resampling rationale](population_weighting_method.md#resampling-method-why-nearest-neighbor-for-population)).

```
Input:  pop_path (GeoTIFF), gridmet_shape, gridmet_transform, gridmet_crs
Output: np.ndarray (float32), shape == gridmet_shape
```

Pre-processing before resampling:
- Source nodata values → 0
- Non-finite (NaN/Inf) values → 0
- Negative values → 0

Grid identity check (`_same_grid()`): if the population raster already matches the gridMET grid exactly (same shape and affine transform within floating-point tolerance), the warp step is skipped entirely.

### `load_population_weights()` — `src/aggregate_gridmet.py`

Wrapper that checks `cfg.population.weighting.enabled`, constructs the file path from `data/{cfg.datapaths.base_path}` and `cfg.year`, calls `align_population_to_gridmet()`, and returns the aligned weight array — or `None` if weighting is disabled or the file is missing.

Returning `None` rather than raising an exception allows `compute_zonal_stats()` to fall back to unweighted aggregation, so a missing population file does not abort the entire pipeline run.

### `compute_zonal_stats()` — `utils/faster_zonal_stats.py`

Computes per-polygon statistics using a precomputed cell-index map (`poly2cells`). The cell map is built once per year/shapefile combination; this is the expensive step. The per-day loop only calls `compute_zonal_stats()`, which is a fast NumPy operation.

```python
# Weighted path (weights is not None):
result = np.sum(valid_cells * valid_weights) / np.sum(valid_weights)

# Unweighted path (weights is None):
result = np.nanmean(valid_cells)
```

NaN values in the meteorological field are excluded from both numerator and denominator via a boolean mask applied before aggregation.

---

## Methodological Considerations

### Downscaling and Population Alignment

When `downscaling_factor > 1`, the gridMET raster is spatially upsampled before polygon aggregation. This is done to improve the accuracy of the polygon-to-cell mapping: at native 2.5 arc-minute (~4.6 km) resolution, small polygons (e.g., dense urban ZCTAs) may intersect only a handful of cells; upsampling by a factor of 4 increases the effective resolution to ~0.625 arc-minutes (~1.16 km), providing finer-grained overlap estimates.

The population raster is **not** upsampled using the same bilinear interpolation as gridMET values. Instead, it is warped to the exact downscaled gridMET grid using nearest-neighbor resampling. This preserves the physical meaning of the population count: each cell in the aligned array holds the count of people residing in the corresponding GPWv4 native cell, assigned to the nearest fine-grid cell. Bilinear interpolation would fractionate and smear counts in a way that has no physical interpretation.

This design follows the principle that spatial transformations should be chosen based on the nature of the data being transformed (Goodchild & Lam, 1980): continuous fields allow smooth interpolation; count data require methods that preserve the discrete character of the values.

### Census Year Assignment

Population data are available only at five-year intervals (2000, 2005, 2010, 2015, 2020). The pipeline assigns the most recent available census year to each meteorological year. This is implemented in `src/download_population.py` via a sorted fallback search. For example, a request for year 2013 resolves to the 2010 population file.

Alternative approaches — linear interpolation between census years, or cohort-component projection — would reduce temporal approximation error but would require additional assumptions and data. The current approach is transparent and reproducible. For most policy-relevant analyses (multi-year time series at county or ZCTA level), the practical impact of this approximation is expected to be small relative to within-county spatial heterogeneity.

### Backward Compatibility

All changes are additive:
- **Default behavior is unweighted.** If `population.weighting.enabled: false` (or the `population` block is absent from the config), the pipeline behaves identically to the pre-weighting version.
- **`compute_zonal_stats()` with `weights=None`** falls back to `np.nanmean`, producing the same result as the previous `rasterstats`-based zonal statistics.
- **Intermediate file format is unchanged.** Downstream stages (format, yearly, seasonal) read the same Parquet schema regardless of whether values were computed with or without population weighting.

---

## Performance

| Operation | Approximate cost |
|-----------|-----------------|
| Population file download | 30–60 s per census year |
| Population grid alignment | 1–2 s per variable-year run |
| Per-day weighted aggregation overhead | +5–10% vs. unweighted |
| Additional memory (population array) | +50–200 MB per run |

The population array is loaded once per variable-year invocation and reused across all 365 daily iterations, so the alignment cost is amortized.

---

## Testing Guidance

### Unit-Level Checks

```python
import numpy as np
from utils.faster_zonal_stats import compute_zonal_stats

# Uniform population → weighted mean == unweighted mean
raster = np.array([[1.0, 2.0], [3.0, 4.0]])
weights = np.ones_like(raster)
cell_map = [(np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1]))]
assert compute_zonal_stats(raster, cell_map, weights=weights) == \
       compute_zonal_stats(raster, cell_map, weights=None)

# All-zero weights → NaN
weights_zero = np.zeros_like(raster)
assert np.isnan(compute_zonal_stats(raster, cell_map, weights=weights_zero)[0])

# Concentrated weight → result biased toward high-weight cell
weights_skewed = np.array([[0.0, 0.0], [0.0, 1.0]])  # all weight on cell (1,1) = value 4.0
result = compute_zonal_stats(raster, cell_map, weights=weights_skewed)[0]
assert abs(result - 4.0) < 1e-6
```

### Integration Check

```bash
python src/aggregate_gridmet.py year=2010 var=tmmx \
    datapaths=cannon_popweighted shapefiles=county \
    population.weighting.enabled=true

python -c "
import pandas as pd
df = pd.read_parquet('data/county/intermediate/tmmx_2010_county.parquet')
assert not df.empty, 'Output is empty'
assert 'tmmx' in df.columns, 'Variable column missing'
assert df['tmmx'].notna().sum() > 0, 'All values are NaN'
print(f'OK: {len(df)} rows, {df[\"tmmx\"].notna().sum()} non-NaN')
"
```

---

## References

- Center for International Earth Science Information Network (CIESIN), Columbia University. (2018). *Gridded Population of the World, Version 4 (GPWv4): Population Count, Revision 11*. NASA SEDAC. https://doi.org/10.7927/H4JW8BX5

- Goodchild, M.F. & Lam, N.S.N. (1980). Areal interpolation: A variant of the traditional spatial problem. *Geo-Processing*, 1, 297–312.

- Tobler, W.R. (1979). Smooth pycnophylactic interpolation for geographical regions. *Journal of the American Statistical Association*, 74(367), 519–530. https://doi.org/10.2307/2286968
