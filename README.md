# gridmet_raster2polygon
Raster to polygon aggregations of gridMET meteorological data. The spatial aggregation are performed for GridMET from grid/raster (NetCDF) to polygons (shp).

---

# GridMET

#TODO incorporate intro

---

# Codebook

## Dataset Columns:

#TODO incorporate dataset columns

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

## Download gridmet pm25 data

#TODO include steps

## Pipeline

You can run the snakemake pipeline described in the Snakefile.

**run snakemake pipeline**
or run the pipeline:

```bash
snakemake --cores 4 
```

Plan around 3GB of RAM per core.

## Dockerized Pipeline

Create the folder where you would like to store the output dataset.

```bash 
mkdir <path>/gridmet_raster2polygon
```

### Pull and Run:

```bash
docker pull nsaph/gridmet_raster2polygon
docker run -v <path>:/app/data/input/gridmet_rasters <path>/gridmet_raster2polygon/:/app/data/output/gridmet_raster2polygon nsaph/gridmet_raster2polygon
```  

If you are interested in storing the input raw and intermediate data run

```bash
docker run -v <path>/gridmet_raster2polygon/:/app/data/ nsaph/gridmet_raster2polygon
```

If you want to build your own image use from the Dockerfile int the GitHub repository.

```bash
docker build -t <image_name> .
docker run [...] <image_name>  # replace [...] with the appropriate arguments
```

