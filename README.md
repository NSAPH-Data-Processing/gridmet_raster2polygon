# gridmet_raster2polygon
Raster to polygon aggregations of gridMET meteorological data. The spatial aggregation are performed for GridMET from grid/raster (NetCDF) to polygons (shp).

---

# GridMET

[gridMET](https://www.climatologylab.org/gridmet.html) combines high-resolution spatial climate data (e.g. temperature, precipitation, humidity) from [PRISM](https://prism.oregonstate.edu) with daily temporal attributes and additional meteorological variables from the regional reanalysis dataset [NLDAS-2](http://ldas.gsfc.nasa.gov/nldas/NLDAS2forcing.php). The resulting product is a dataset of daily meteorological variables at ~4km x 4km resolution across the contiguous U.S. 

---

# Run

## Conda environment

Clone the repository and create a conda environment.

```bash
git clone <https://github.com/<user>/repo>
cd <repo>

conda env create -f requirements.yml
conda activate <env_name> #environment name as found in requirements.yml
```

It is also possible to use `mamba`.

```bash
mamba env create -f requirements.yml
mamba activate <env_name>
```

## Input and output paths

Determine the configuration file to be used in `cfg.datapaths`. The `input`, `intermediate`, and `output` arguments are used in `utils/create_dir_paths.py` to fix the paths or directories from which a step in the pipeline reads/writes its input/output data inside the corresponding `/data` subfolders.

If `cfg.datapaths` points to `<input_path>` or `<output_path>`, then `utils/create_dir_paths.py` will automatically create a symlink as in the following example:

```bash
export HOME_DIR=$(pwd)

cd $HOME_DIR/data/input/ .
ln -s <input_path> . 

cd $HOME_DIR/data/output/
ln -s <output_path> . 
```

## Using custom shapefiles

It is also possible to run this script to aggregate based on your own custom shapefile. In order to do this, follow these steps:

1. Create a `conf/datapaths/{shapefile_name}.yaml` that contains the desired locations for input, intermediate, and output files. An example is given with `county_cannon.yaml`. Leaving any entries as `null` means files will be stored locally for that directory (no symlink).
2. Create a `conf/shapefiles/{shapefile_name}.yaml` with important metadata for your shapefile. For what years is it available? What is the ID column (usually `GEOID`)? What is the base naming format?
    a. Note: this pipeline expects shapefiles to be stored in paths of the form `{shapefile_prefix}_{shapefile_year}/{shapefile_prefix}_{shapefile_year}.shp`
3. Modify `conf/snakemake.yaml` as necessary. This config file controls what years, what geographic levels, and what gridmet variables the pipeline will process.
4. Run `python3 create_dir_paths.py` to create the file directory structure for the pipeline.
5. 

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

