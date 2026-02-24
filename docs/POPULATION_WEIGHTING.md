# Population-Weighted gridMET Aggregation

This document explains how to use population weighting when aggregating gridMET meteorological variables to polygons (counties, ZCTAs, etc.).

## Overview

Population weighting provides a more accurate representation of human exposure to meteorological conditions by giving greater weight to grid cells with higher populations. Instead of a simple spatial average, population-weighted aggregation computes:

```
weighted_mean = Σ(value_i × population_i) / Σ(population_i)
```

This is particularly important for:
- Health studies examining human exposure to temperature extremes
- Epidemiological analyses relating weather to health outcomes
- Environmental justice studies
- Urban vs. rural climate exposure patterns

## Data Source

Population data is sourced from Harvard Dataverse:

**Population Count**: https://doi.org/10.7910/DVN/C0LVYI
- Annual population counts at 1km × 1km grid resolution
- Contiguous United States coverage

## Configuration

### Enabling Population Weighting

Edit `conf/population.yaml`:

```yaml
weighting:
  enabled: true  # Set to true to enable population weighting
  method: mean   # Currently only 'mean' is supported
```

### Adding Population Data Files

You need to add file information to `conf/population.yaml` for the years you want to process. Visit the Dataverse links above to find file IDs or download URLs:

```yaml
count:
  file_map:
    2010:
      filename: "population_count_2010.tif"
      file_id: "123456"  # Get this from Dataverse
      url: null          # Or provide direct URL
    2020:
      filename: "population_count_2020.tif"
      file_id: "234567"
      url: null
```

## Usage

### Step 1: Download Population Data

Download population data for the years you need:

```bash
# Download population count data for 2010
python src/download_population.py year=2010

# Download for multiple years
for year in {2000..2020}; do
    python src/download_population.py year=$year
done
```

### Step 2: Enable Weighting in Configuration

Edit `conf/population.yaml` and set `weighting.enabled: true`

### Step 3: Run Aggregation Pipeline

Run the standard pipeline - it will automatically use population weights:

```bash
# For a single year and variable
python src/aggregate_gridmet.py year=2010 var=tmmx datapaths=county_core_cannon shapefiles=county

# Or use Snakemake for the full pipeline
snakemake --cores 8 -C datapaths=county_core_cannon shapefiles=county years=[2010,2020]
```

### Running with Snakemake (Optional Population Download)

If you want Snakemake to handle population download as well:

```bash
# This will download population data as needed
snakemake --cores 8 \
    -C datapaths=county_core_cannon shapefiles=county \
    --config population_enabled=true
```

## Comparing Weighted vs Unweighted Results

To compare results:

```bash
# 1. Run with weighting disabled
python src/aggregate_gridmet.py year=2010 var=tmmx population.weighting.enabled=false

# 2. Run with weighting enabled
python src/aggregate_gridmet.py year=2010 var=tmmx population.weighting.enabled=true

# Results will be saved to different output files
```

## Technical Details

### Spatial Alignment

The population data and gridMET data are automatically aligned:
- gridMET: 4km × 4km resolution (standard) or 1km with downscaling
- Population: 1km × 1km resolution
- Both use consistent geographic coordinate systems

The aggregation process:
1. Loads population and gridMET rasters
2. Applies same downscaling factor to both
3. Computes weighted statistics using overlapping grid cells
4. Aggregates to polygon level

### Handling Missing Data

- Population cells with negative values are set to 0
- NaN values in population are set to 0
- Grid cells with no population receive zero weight
- If population data is missing for a year, falls back to unweighted aggregation

### Memory Considerations

Population-weighted aggregation requires loading an additional raster layer:
- Population raster: ~50-200 MB per year (depending on resolution)
- Memory increase: ~10-20% compared to unweighted aggregation

## Output Files

Output files follow the same naming convention:
```
meteorology__gridmet__{polygon_name}_{temporal}__{year}.parquet
```

Columns remain the same (e.g., `tmmx`, `tmmn`, `pr`, etc.), but values represent population-weighted means when weighting is enabled.

**Important**: To distinguish between weighted and unweighted outputs, use different datapath configurations:
- `datapaths=county_core_cannon` - for standard (unweighted) 
- Create `datapaths=county_weighted_cannon` - for population-weighted

## Example: County-Level Analysis

Full workflow for population-weighted county-level gridMET:

```bash
# 1. Download population data for years of interest
for year in {2000..2024}; do
    python src/download_population.py population_type=count year=$year
done

# 2. Enable weighting in configuration
# Edit conf/population.yaml: weighting.enabled: true

# 3. Run the full pipeline
snakemake --cores 16 \
    -C datapaths=county_core_cannon shapefiles=county \
    years=[2000,2024]

# Output files will be in:
# /n/dominici_lab/lab/lego/environmental/meteorology__gridmet/core/county/output/
#   - daily/meteorology__gridmet__county_daily__{year}.parquet
#   - yearly/meteorology__gridmet__county_yearly__{year}.parquet
#   - seasonal/meteorology__gridmet__county_seasonal__{year}.parquet
```

## Validation and Quality Checks

After running population-weighted aggregation:

1. **Check population totals**: Verify total population in logs
2. **Compare with unweighted**: Run both methods and compare results for urban vs rural areas
3. **Spot check**: Urban counties should show different values than unweighted
4. **NaN values**: Ensure no unexpected missing values

## References

- Population data methodology: See Dataverse documentation
- gridMET data: Abatzoglou, J.T. (2013). Development of gridded surface meteorological data
- Weighted aggregation: Standard population-weighted averaging methodology

## Troubleshooting

**Population file not found**: 
```
ERROR: Population file not found: /path/to/file.tif
```
Solution: Run `python src/download_population.py year=XXXX`

**Memory errors**:
Solution: Reduce number of parallel Snakemake jobs or process fewer years at once

**Population data missing for year**:
Solution: Check available years in `conf/population.yaml` file_map

**Different results than expected**:
Solution: Verify `weighting.enabled: true` in config and check log messages confirming weighted aggregation is being used
