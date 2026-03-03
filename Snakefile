import yaml
import os
import hydra
from src.aggregate_gridmet import available_shapefile_year

conda: "requirements.yaml"
configfile: "conf/snakemake.yaml"


envvars:
    "PYTHONPATH",  # this indicates that the PYTHONPATH must be set, always done in docker


years = list(range(config["years"][0], config["years"][1] + 1))
vars = config["gridmet_vars"]
shapefiles = config["shapefiles"]
datapaths = config["datapaths"]  # cannon_core or cannon_popweighted

# == Load config as hydra with defaults ==
overrides = [f"datapaths={datapaths}", f"shapefiles={shapefiles}"]
with hydra.initialize(version_base=None, config_path="conf"):
    hydra_cfg = hydra.compose(config_name="config", overrides=overrides)

geo_name = hydra_cfg.datapaths.name
# Resolve data root: consolidated configs (name=null) append polygon_name to base_path
base_path = getattr(hydra_cfg.datapaths, 'base_path', None)
if geo_name is not None:
    data_root = base_path or f"data/{geo_name}"
else:
    data_root = f"{base_path}/{shapefiles}"

# needed to import modules from utils/ when running aggregate_gridmet.py
if "PYTHONPATH" in os.environ:
    os.environ["PYTHONPATH"] += ":."

print(f"geo_name resolved to: {geo_name}")
print(f"data_root resolved to: {data_root}")

# == Define rules ==
rule all:
    input:
        expand(
            f"{data_root}/output/yearly/meteorology__gridmet__{shapefiles}_yearly__{{year}}.parquet",
            year=years
        ),

rule download_gridmet:
    output:
        f"{data_root}/input/raw/{{var}}_{{year}}.nc",
    log:
        err="logs/download_gridmet_{var}_{year}.log",
    shell:
        "python src/download_gridmet.py year={wildcards.year} var={wildcards.var} datapaths={datapaths} shapefiles={shapefiles} 2> {log.err}"

rule download_population:
    output:
        "data/input/population/count/gpw-v4-population-count-rev11_{year}_2pt5_min_tif.zip",
    log:
        err="logs/download_population_{year}.log",
    shell:
        "python src/download_population.py year={wildcards.year} 2> {log.err}"

rule aggregate_gridmet:
    input:
        gridmet=f"{data_root}/input/raw/{{var}}_{{year}}.nc",
        population="data/input/population/count/gpw-v4-population-count-rev11_{year}_2pt5_min_tif.zip" if hydra_cfg.population.weighting.enabled else [],
    output:
        f"{data_root}/intermediate/{{var}}_{{year}}_{shapefiles}.parquet",
    log:
        f"logs/{shapefiles}/aggregate_gridmet_{{var}}_{{year}}_{shapefiles}.log",
    params:
        overrides=" ".join(overrides),  # pass hydra overrides (here just shapefiles)
    shell:
        """
        python src/aggregate_gridmet.py year={wildcards.year} var={wildcards.var} {params.overrides} \
             &> {log}
        """

rule format_gridmet:
    input:
        expand(
            f"{data_root}/intermediate/{{var}}_{{year}}_{shapefiles}.parquet",
            var=vars, 
            year="{year}"
        ),
    output:
        f"{data_root}/output/daily/meteorology__gridmet__{shapefiles}_daily__{{year}}.parquet",
    log:
        f"logs/{shapefiles}/format_gridmet_{{year}}.log",
    shell:
        """
        python src/format_gridmet.py year={wildcards.year} datapaths={datapaths} shapefiles={shapefiles}
        """

rule get_yearly:
    input:
        f"{data_root}/output/daily/meteorology__gridmet__{shapefiles}_daily__{{year}}.parquet",
    output:
        f"{data_root}/output/yearly/meteorology__gridmet__{shapefiles}_yearly__{{year}}.parquet",
    log:
        f"logs/{shapefiles}/get_yearly_{{year}}.log",
    shell:
        """
        python src/get_yearly.py year={wildcards.year} datapaths={datapaths} shapefiles={shapefiles}
        """
