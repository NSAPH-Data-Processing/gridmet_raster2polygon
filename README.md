# gridmet_raster2polygon
Raster to polygon aggregations of gridMET meteorological data. The spatial aggregation are performed for GridMET from grid/raster (NetCDF) to polygons (shp).

---

# GridMET

[gridMET](https://www.climatologylab.org/gridmet.html) combines high-resolution spatial climate data (e.g. temperature, precipitation, humidity) from [PRISM](https://prism.oregonstate.edu) with daily temporal attributes and additional meteorological variables from the regional reanalysis dataset [NLDAS-2](http://ldas.gsfc.nasa.gov/nldas/NLDAS2forcing.php). The resulting product is a dataset of daily meteorological variables at ~4km x 4km resolution across the contiguous U.S. 

---

# Codebook

## Dataset Columns:

- GEOID `{string}`: Geographic ID of aggregation level (U.S. County, ZCTA, or grid cell).  
- `year` `{int}`: Dataset year.  
- `sph` `{float64}`: Specific humidity (kg/kg), representing the mass of water vapor per unit mass of air.  
- `vpd` `{float64}`: Vapor pressure deficit (hPa), which measures the difference between the amount of moisture in the air and how much moisture the air can hold when saturated.  
- `tmmn` `{float64}`: Minimum daily temperature (Kelvin).  
- `tmmx` `{float64}`: Maximum daily temperature (Kelvin).  
- `pr` `{float64}`: Precipitation (mm), total daily precipitation.  
- `rmin` `{float64}`: Minimum relative humidity (%), the lowest daily relative humidity recorded.  
- `rmax` `{float64}`: Maximum relative humidity (%), the highest daily relative humidity recorded.  
- `srad` `{float64}`: Downward shortwave solar radiation (W/m²), measuring the solar energy received at the surface.  
- `vs` `{float64}`: Wind speed at 10 meters (m/s), representing the average daily wind speed at 10 meters above ground level.  
- `th` `{float64}`: Wind direction at 10 meters (degrees from north), indicating the direction from which the wind is blowing.  

---

# Pipeline Overview

## Data Processing Workflow

The pipeline transforms gridMET raster data (NetCDF format) into aggregated polygon-level statistics through several stages:

### 1. Download (`download_gridmet.py`)
- Downloads raw gridMET NetCDF files from the [gridMET repository](https://www.climatologylab.org/gridmet.html)
- One file per variable per year
- **Output:** `data/{product}/{polygon_name}/input/raw/{var}_{year}.nc`

### 2. Aggregate (`aggregate_gridmet.py`)
- Performs zonal statistics to aggregate raster grid cells to polygon boundaries (counties, ZCTAs, or custom shapefiles)
- Uses weighted averages based on the overlap between grid cells and polygons
- Processes each variable and year independently
- **Output:** `data/{product}/{polygon_name}/intermediate/{var}_{year}_{polygon_name}.parquet`

### 3. Format (`format_gridmet.py`)
- Joins all meteorological variables into a single daily dataset
- Ensures data consistency and removes null values
- Creates a unified time series with all variables for each geographic unit
- **Output:** `data/{product}/{polygon_name}/output/daily/meteorology__gridmet__{product}__{polygon_name}_daily__{year}.parquet`

### 4. Yearly Aggregates (`get_yearly.py`)
- Calculates annual average for each meteorological variable
- Groups by geographic unit (county/ZCTA/grid cell)
- **Output:** `data/{product}/{polygon_name}/output/yearly/meteorology__gridmet__{product}__{polygon_name}_yearly__{year}.parquet`
- **Columns:** `{polygon_name}`, `year`, and average values for each gridMET variable

### 5. Seasonal Aggregates (`seasonal_vars.py`)
- Calculates seasonal averages based on configurable season definitions (see `conf/seasons.yaml`)
- **Default seasons:**
  - **Summer:** June, July, August
  - **Winter:** December, January, February (all from the same calendar year)
  - Additional seasons can be configured in `conf/seasons.yaml`
- Each season's variables are suffixed with the season name (e.g., `tmmx_summer`, `pr_winter`)
- **Output:** `data/seasonal/{polygon_name}/output/yearly/meteorology__gridmet__seasonal__{polygon_name}_yearly__{year}.parquet`
- **Columns:** `{polygon_name}`, `year`, and seasonal averages (e.g., `tmmx_summer`, `tmmn_winter`, etc.)

## Output Files

All outputs are stored in Parquet format for efficient storage and fast querying:

### Daily Data
- **Path:** `data/{product}/{polygon_name}/output/daily/meteorology__gridmet__{product}__{polygon_name}_daily__{year}.parquet`
- **Granularity:** Daily values for each geographic unit
- **Columns:** Geographic ID, date, and all 11 gridMET variables

### Yearly Data
- **Path:** `data/{product}/{polygon_name}/output/yearly/meteorology__gridmet__{product}__{polygon_name}_yearly__{year}.parquet`
- **Granularity:** Annual averages for each geographic unit
- **Columns:** Geographic ID, year, and mean values for all 11 gridMET variables

### Seasonal Data
- **Path:** `data/seasonal/{polygon_name}/output/yearly/meteorology__gridmet__seasonal__{polygon_name}_yearly__{year}.parquet`
- **Granularity:** Seasonal averages for each geographic unit
- **Columns:** Geographic ID, year, and season-specific mean values (e.g., `tmmx_summer`, `pr_winter`)

## Customizing Seasons

Seasonal definitions are configured in `conf/seasons.yaml`. Each season specifies:
- `months`: List of month numbers (1=January, 12=December)

Example configuration:
```yaml
summer:
  months: [6, 7, 8]  # June, July, August

winter:
  months: [12, 1, 2]  # December, January, February
```

# Run

## Conda environment

Clone the repository and create a conda environment.

```bash
git clone <https://github.com/<user>/repo>
cd <repo>

conda env create -f requirements.yaml
conda activate <env_name> #environment name as found in requirements.yaml
```

It is also possible to use `mamba`.

```bash
mamba env create -f requirements.yaml
mamba activate <env_name>
```

## Input and output paths

Determine the configuration file to be used in `cfg.datapaths`. The `base_path` value is the product key used below `data/` and in final filenames, such as `core`, `population_weighted`, or `seasonal`. The `input`, `intermediate`, and `output` arguments are used in `utils/create_dir_paths.py` to fix the paths or directories from which a step in the pipeline reads/writes its input/output data inside the corresponding `/data/{base_path}` subfolders.

If `cfg.datapaths` points to `<input_path>` or `<output_path>`, then `utils/create_dir_paths.py` will automatically create a symlink as in the following example:

```bash
export HOME_DIR=$(pwd)

cd $HOME_DIR/data/input/ .
ln -s <input_path> . 

cd $HOME_DIR/data/output/
ln -s <output_path> . 
```

## Using custom shapefiles

It is also possible to run this script to aggregate based on your own custom shapefile. In order to do this, follow the following steps:

1. Create a `conf/datapaths/{shapefile_name}.yaml` that contains the locations of input, intermediate, and output files. An example is given with `county_cannon.yaml`.
2. Create a `conf/shapefiles/{shapefiles_name}.yaml` with important metadata for your shapefile. The following metadata is required:
    - `years`: Available shapefile years (list) 
    - `idvar`: ID column name
    - `shapefile_prefix`: Base naming format
3. Modify the `datapaths` and `shapefile` entries in `conf/config.yaml` to match these new config files. For example:

```yaml
    defaults:
    - _self_
    - datapaths: grid4x4_cannon
    - gridmet
    - shapefiles: grid_4x4km 
```
NB: this pipeline expects shapefiles to be stored in paths of the form `{shapefile_prefix}_{shapefile_year}/{shapefile_prefix}_{shapefile_year}.shp`

## Population Weighting (Optional)

This pipeline supports **population-weighted aggregation** of gridMET variables. Simple spatial averages treat each grid cell equally regardless of how many people reside there; population-weighted aggregation instead computes:

```
weighted_mean = Σ(value_i × population_i) / Σ(population_i)
```

This approach is the methodological standard in climate-health epidemiology, where the goal is to characterize **human exposure** rather than areal coverage (Gasparrini et al., 2015; Zhao et al., 2021). It ensures that densely populated urban areas which tend to exhibit distinct microclimates from surrounding rural land contribute proportionally to their population share.

Population counts are drawn from the Gridded Population of the World, Version 4 (GPWv4), Revision 11 (CIESIN, 2018) at 2.5 arc-minute (~4.6 km) resolution and are automatically aligned to the gridMET grid.

### Quick Start

1. **Enable population weighting** in `conf/population.yaml`:
   ```yaml
   weighting:
     enabled: true
   ```

2. **Download population data**:
   ```bash
   python src/download_population.py population_type=count year=2010
   ```

3. **Run the pipeline** (weighting will be automatically applied):
   ```bash
   snakemake --cores 4
   ```

### Data Source

- **Population Count (GPWv4 Rev. 11)**: https://doi.org/10.7910/DVN/C0LVYI

### Documentation

For full scientific background, methodological rationale, limitations, and usage instructions, see: **[docs/population_weighting_method.md](docs/population_weighting_method.md)**

### Selected References

- CIESIN (2018). *Gridded Population of the World, Version 4 (GPWv4): Population Count, Revision 11*. NASA SEDAC. https://doi.org/10.7927/H4JW8BX5
- Gasparrini, A., et al. (2015). Mortality risk attributable to high and low ambient temperature: a multicountry observational study. *The Lancet*, 386(9991), 369–375. https://doi.org/10.1016/S0140-6736(14)62114-0
- Zhao, Q., et al. (2021). Global, regional, and national burden of mortality associated with non-optimal ambient temperatures from 2000 to 2019. *Lancet Planetary Health*, 5(7), e415–e425. https://doi.org/10.1016/S2542-5196(21)00081-4

## Pipeline

You can run the snakemake pipeline described in the Snakefile.

**run snakemake pipeline**
or run the pipeline:

```bash
export PYTHONPATH="."
snakemake --cores 4 
```

## Dockerized Pipeline

Create the folder where you would like to store the output dataset.

```bash 
mkdir <path>
```

### Pull and Run:

```bash
docker pull nsaph/gridmet_raster2polygon
docker run -v <path>:/app/data/ nsaph/gridmet_raster2polygon
``` 

If you want to build your own image use from the Dockerfile int the GitHub repository.

```bash
docker build -t <image_name> .
```
