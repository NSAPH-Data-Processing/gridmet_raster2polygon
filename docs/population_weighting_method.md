# Population-Weighted gridMET Aggregation

## Overview

This document describes the scientific rationale, data sources, mathematical formulation, and usage instructions for population-weighted aggregation of gridMET meteorological variables in the `gridmet_raster2polygon` pipeline.

---

## Scientific Background

### Motivation

Simple spatial (arithmetic) averaging assigns equal weight to every raster grid cell that intersects a polygon, regardless of the number of people who live within it. This is appropriate when the quantity of interest is a physical property of the landscape (e.g., total watershed runoff), but it is inappropriate when the goal is to characterize **human exposure** to meteorological conditions.

In climate-health epidemiology, the standard practice is to weight meteorological estimates by the population distribution within each administrative unit. A rural county with uniformly sparse settlement may show little difference between weighted and unweighted estimates; but a large, heterogeneous county containing a dense urban core surrounded by agricultural land can exhibit substantial differences, because the urban population, which may experience an urban heat island effect or different humidity regimes, dominates the weighted estimate.

This approach has been adopted widely in the environmental health literature. Gasparrini et al. (2015) used population-weighted temperature exposure across 13 countries to estimate attributable mortality. Zhao et al. (2021) applied population-weighted gridded climate data globally to estimate the burden of non-optimal ambient temperatures. Diffenbaugh & Burke (2019) used population-weighted growing-season temperatures to assess the distributional consequences of global warming. In each case, weighting by population produces exposure estimates that better reflect the experience of the population under study than unweighted spatial means.

### Epidemiological Context

The pipeline is designed to support analyses linking daily meteorological exposure to health outcomes — temperature–mortality relationships, heat wave impacts, respiratory and cardiovascular disease burden — where the unit of analysis is typically a county or ZIP Code Tabulation Area (ZCTA). In such studies:

- **Ecological exposure misclassification** is a key concern: if the meteorological value assigned to a county does not represent where people actually live, associations can be biased toward the null or in unpredictable directions.
- **Urban-rural heterogeneity** within administrative units is large: a single U.S. county can span dense city centers and unpopulated mountain terrain.
- **Temporal consistency** requires that the same weighting scheme is applied across all years and variables.

Population weighting addresses all three concerns by anchoring meteorological estimates to where people reside.

---

## Mathematical Formulation

For a given polygon *p* (county, ZCTA, etc.) and a given day *t*, the population-weighted mean of meteorological variable *X* is:

$$\bar{X}_{p,t} = \frac{\sum_{i \in \mathcal{C}_p} X_{i,t} \cdot w_i}{\sum_{i \in \mathcal{C}_p} w_i}$$

where:

- $\mathcal{C}_p$ is the set of raster grid cells whose centroids (or touched area) fall within polygon $p$
- $X_{i,t}$ is the gridMET value for cell $i$ on day $t$
- $w_i$ is the population count for cell $i$ (from GPWv4)
- Cells where $X_{i,t}$ is missing (NaN) are excluded from both numerator and denominator

If $\sum_{i \in \mathcal{C}_p} w_i = 0$ (no population in the polygon), the result is `NaN`. This can occur for uninhabited polygons (e.g., offshore ZCTAs or national park counties) and is the correct behavior — assigning a population-weighted mean to an area with no population is undefined.

The unweighted (arithmetic) mean is the special case where $w_i = 1\ \forall\ i$:

$$\bar{X}_{p,t}^{\text{unweighted}} = \frac{1}{|\mathcal{C}_p|} \sum_{i \in \mathcal{C}_p} X_{i,t}$$

---

## Data Sources

### gridMET Meteorological Data

gridMET (Abatzoglou, 2013) is a daily, gridded surface meteorological dataset covering the contiguous United States at approximately 4 km × 4 km spatial resolution (~1/24°, or 2.5 arc-minutes). It is produced by statistically merging the high-resolution spatial climatology of PRISM (Daly et al., 2008) with the temporal dynamics of NLDAS-2 (Xia et al., 2012). The result is a dataset that preserves the spatial detail of PRISM while maintaining the temporal accuracy of the reanalysis.

**Citation:** Abatzoglou, J.T. (2013). Development of gridded surface meteorological data for ecological applications and modelling. *International Journal of Climatology*, 33(1), 121–131. https://doi.org/10.1002/joc.3413

### Population Data (GPWv4)

Population counts are drawn from the **Gridded Population of the World, Version 4 (GPWv4), Revision 11**, produced by the Center for International Earth Science Information Network (CIESIN) at Columbia University and distributed through NASA's Socioeconomic Data and Applications Center (SEDAC).

GPWv4 distributes national census data into equal-area grid cells using areal weighting, without assumptions about the sub-unit distribution of population (i.e., no dasymetric mapping). This makes it a transparent, reproducible choice for spatial weighting. Census data are collected for the following target years and obtained from the Harvard Dataverse mirror:

| Year | Resolution | DOI (Dataverse) |
|------|-----------|-----------------|
| 2000 | 2.5 arc-min | https://doi.org/10.7910/DVN/C0LVYI |
| 2005 | 2.5 arc-min | https://doi.org/10.7910/DVN/C0LVYI |
| 2010 | 2.5 arc-min | https://doi.org/10.7910/DVN/C0LVYI |
| 2015 | 2.5 arc-min | https://doi.org/10.7910/DVN/C0LVYI |
| 2020 | 2.5 arc-min | https://doi.org/10.7910/DVN/C0LVYI |

**Citation:** Center for International Earth Science Information Network (CIESIN), Columbia University. (2018). *Gridded Population of the World, Version 4 (GPWv4): Population Count, Revision 11*. Palisades, NY: NASA Socioeconomic Data and Applications Center (SEDAC). https://doi.org/10.7927/H4JW8BX5

---

## Spatial Alignment and Resampling

### Native Grid Resolutions

Both gridMET and GPWv4 are distributed at 2.5 arc-minute (~4.6 km at the equator) resolution. This shared native resolution simplifies alignment: the two grids differ only in origin offset, which is corrected by the `align_population_to_gridmet()` function using affine transform comparison and nearest-neighbor reprojection.

### Downscaling

When `downscaling_factor > 1` (default: 4), gridMET values are spatially interpolated to a finer grid before polygon aggregation. With a factor of 4, the effective gridMET resolution becomes 0.625 arc-minutes (~1.16 km at mid-latitudes). At this resolution, the gridMET grid is finer than the native GPWv4 grid (2.5 arc-min); the population raster is then warped to match the downscaled gridMET grid.

### Resampling Method: Why Nearest-Neighbor for Population

The pipeline uses **different resampling methods** for gridMET values and population counts, and this distinction is methodologically important:

- **gridMET values** are resampled using **bilinear interpolation** (`scipy.ndimage.zoom`, `order=1`). Temperature, precipitation, and humidity are continuous fields; interpolating between adjacent cells produces physically reasonable intermediate values.

- **Population counts** are resampled using **nearest-neighbor** resampling (`rasterio.warp.Resampling.nearest`). Population is a discrete count per pixel, not a continuous field. Interpolating between population cells would fractionate integer counts and artificially smooth the spatial distribution of people, introducing bias in the weights. Nearest-neighbor resampling instead assigns to each fine-grid cell the population value of the nearest coarse-grid cell, preserving the integrity of the count data.

This distinction follows established practice in spatial data handling: continuous variables are interpolated, while count data and categorical variables are resampled by nearest-neighbor or mode methods.

---

## Population Year Assignment

GPWv4 provides population estimates for 2000, 2005, 2010, 2015, and 2020 only. For meteorological years that fall between census years, this pipeline applies the **most recent preceding census year** as the population weight:

| Meteorological years | Population year used |
|---------------------|---------------------|
| 2000–2004 | 2000 |
| 2005–2009 | 2005 |
| 2010–2014 | 2010 |
| 2015–2019 | 2015 |
| 2020–present | 2020 |



---

## Configuration

### Enabling Population Weighting

Edit `conf/population.yaml`:

```yaml
weighting:
  enabled: true   # Set to false to use simple spatial averaging
  method: mean    # Only population-weighted mean is currently supported
```

### Confirming Active Configuration

Check the log output at runtime — the pipeline explicitly logs whether weighted or unweighted aggregation is active:

```
INFO - Using population-weighted aggregation (count)
INFO - Total population (aligned): 328,239,523
```

---

## Usage

### Step 1: Download Population Data

```bash
# Download for a single census year
python src/download_population.py year=2010

# Download all available census years
for year in 2000 2005 2010 2015 2020; do
    python src/download_population.py year=$year
done
```

The script resolves the correct file from Harvard Dataverse, caches the raw zip, extracts the GeoTIFF, and saves it to:
```
data/{base_path}/population/output/world_population__sedac__world_yearly__{year}.tif
```

### Step 2: Run Aggregation

Run the standard Snakemake pipeline — population weighting is applied automatically when enabled:

```bash
snakemake --cores 8
```

Or run a single variable/year directly:

```bash
python src/aggregate_gridmet.py year=2010 var=tmmx datapaths=cannon_popweighted shapefiles=county
```

### Step 3: Compare Weighted vs. Unweighted (Optional)

```python
import pandas as pd

weighted   = pd.read_parquet("data/population_weighted/county/output/daily/meteorology__gridmet__population_weighted__county_daily__2010.parquet")
unweighted = pd.read_parquet("data/core/county/output/daily/meteorology__gridmet__core__county_daily__2010.parquet")

# Expect larger divergence in heterogeneous urban counties
nyc_diff   = weighted.loc['36061', 'tmmx'] - unweighted.loc['36061', 'tmmx']  # New York County
rural_diff = weighted.loc['31005', 'tmmx'] - unweighted.loc['31005', 'tmmx']  # Arthur County, NE

print(f"NYC difference:   {nyc_diff:.2f} K")
print(f"Rural difference: {rural_diff:.2f} K")
```

---

## Handling Missing and Invalid Data

| Condition | Treatment |
|-----------|-----------|
| Negative population values | Set to 0 before weighting |
| Non-finite (NaN/Inf) population | Set to 0 before weighting |
| Missing gridMET value for a cell | Cell excluded from both numerator and denominator |
| Polygon with zero total weight | Assigned `NaN` (undefined exposure) |
| Population file not found | Falls back to unweighted aggregation with a warning |

The fallback to unweighted aggregation ensures the pipeline does not silently fail when population data is unavailable for a given year; all fallback events are logged at `WARNING` level.

---

## Output Files

Output files follow the same naming convention and column schema as unweighted outputs:

```
{data_root}/intermediate/{var}_{year}_{polygon_name}.parquet
{data_root}/output/daily/meteorology__gridmet__{product}__{polygon_name}_daily__{year}.parquet
{data_root}/output/yearly/meteorology__gridmet__{product}__{polygon_name}_yearly__{year}.parquet
```

Columns are identical (e.g., `tmmx`, `tmmn`, `pr`), but values represent population-weighted means when weighting is enabled. To maintain traceability, use separate `datapaths` configurations for weighted and unweighted runs (e.g., `cannon_popweighted` vs. `cannon_core`).

---

## Limitations and Caveats

1. **Population year approximation.** Using the most recent preceding census year introduces temporal approximation for mid-decade meteorological years. Rapidly growing or declining counties may have non-trivial error.

2. **Sub-grid population distribution.** GPWv4 distributes census-unit population uniformly within each 2.5 arc-minute cell. At the county or ZCTA level, this is rarely a source of substantial bias, but researchers working in areas with highly clustered settlement (e.g., small island territories, very sparse rural counties) should verify that the spatial distribution of GPWv4 counts is reasonable.

3. **Uninhabited polygons.** ZCTAs or counties covering exclusively water, wilderness, or other uninhabited areas will produce `NaN` for all population-weighted meteorological variables. This is correct behavior.

---

## Validation

After running population-weighted aggregation:

1. **Check log-reported totals.** The pipeline logs total aligned population; verify this matches known CONUS population figures for the census year used.
2. **Compare urban vs. rural counties.** Dense urban counties (e.g., New York County, NY; San Francisco County, CA) should show the largest weighted–unweighted divergence.
3. **Check for unexpected NaN patterns.** Widespread unexpected NaN in the output indicates a grid alignment failure; verify that the population file exists and that the affine transform is consistent.
4. **Year-over-year stability.** Population-weighted estimates should be temporally smooth between adjacent years; large discontinuities at census boundaries (e.g., 2009→2010) may indicate alignment issues.

---

## References

- Abatzoglou, J.T. (2013). Development of gridded surface meteorological data for ecological applications and modelling. *International Journal of Climatology*, 33(1), 121–131. https://doi.org/10.1002/joc.3413

- Center for International Earth Science Information Network (CIESIN), Columbia University. (2018). *Gridded Population of the World, Version 4 (GPWv4): Population Count, Revision 11*. Palisades, NY: NASA Socioeconomic Data and Applications Center (SEDAC). https://doi.org/10.7927/H4JW8BX5

- Daly, C., Halbleib, M., Smith, J.I., Gibson, W.P., Doggett, M.K., Taylor, G.H., Curtis, J., & Pasteris, P.P. (2008). Physiographically sensitive mapping of climatological temperature and precipitation across the conterminous United States. *International Journal of Climatology*, 28(15), 2031–2064. https://doi.org/10.1002/joc.1688

- Diffenbaugh, N.S. & Burke, M. (2019). Global warming has increased global economic inequality. *Proceedings of the National Academy of Sciences*, 116(20), 9808–9813. https://doi.org/10.1073/pnas.1816020116

- Gasparrini, A., Guo, Y., Hashizume, M., Lavigne, E., Zanobetti, A., Schwartz, J., … Armstrong, B. (2015). Mortality risk attributable to high and low ambient temperature: a multicountry observational study. *The Lancet*, 386(9991), 369–375. https://doi.org/10.1016/S0140-6736(14)62114-0

- Xia, Y., Mitchell, K., Ek, M., Sheffield, J., Cosgrove, B., Wood, E., … Luo, L. (2012). Continental-scale water and energy flux analysis and validation for the North American Land Data Assimilation System project phase 2 (NLDAS-2): 1. Intercomparison and application of model products. *Journal of Geophysical Research: Atmospheres*, 117, D03109. https://doi.org/10.1029/2011JD016048

- Zhao, Q., Guo, Y., Ye, T., Gasparrini, A., Tong, S., Overcenco, A., … & Li, S. (2021). Global, regional, and national burden of mortality associated with non-optimal ambient temperatures from 2000 to 2019: a three-stage modelling study. *Lancet Planetary Health*, 5(7), e415–e425. https://doi.org/10.1016/S2542-5196(21)00081-4
