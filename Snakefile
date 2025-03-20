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
datapaths = config["datapaths"]  # This should match a valid datapaths config name

# == Load config as hydra with defaults ==
overrides = [f"datapaths={datapaths}", f"shapefiles={shapefiles}"]
with hydra.initialize(version_base=None, config_path="conf"):
    hydra_cfg = hydra.compose(config_name="config", overrides=overrides)

geo_name = hydra_cfg.datapaths.name

# needed to import modules from utils/ when running aggregate_gridmet.py
if "PYTHONPATH" in os.environ:
    os.environ["PYTHONPATH"] += ":."

print(f"geo_name resolved to: {geo_name}")

# == Define rules ==
rule all:
    input:
        expand(
            f"data/{geo_name}/output/yearly/meteorology__gridmet__{shapefiles}_yearly__{{year}}.parquet",
            year=years
        ),

rule download_gridmet:
    output:
        f"data/{geo_name}/input/raw/{{var}}_{{year}}.nc",
    log:
        err="logs/download_gridmet_{var}_{year}.log",
    shell:
        "python src/download_gridmet.py year={wildcards.year} var={wildcards.var} 2> {log.err}"

rule aggregate_gridmet:
    input:
        f"data/{geo_name}/input/raw/{{var}}_{{year}}.nc",
    output:
        f"data/{geo_name}/intermediate/{{var}}_{{year}}_{shapefiles}.parquet",
    log:
        f"logs/{geo_name}/aggregate_gridmet_{{var}}_{{year}}_{shapefiles}.log",
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
            f"data/{geo_name}/intermediate/{{var}}_{{year}}_{shapefiles}.parquet",
            var=vars, 
            year="{year}"
        ),
    output:
        f"data/{geo_name}/output/daily/meteorology__gridmet__{shapefiles}_daily__{{year}}.parquet",
    log:
        f"logs/{geo_name}/format_gridmet_{{year}}.log",
    shell:
        """
        python src/format_gridmet.py year={wildcards.year}
        """

rule get_yearly:
    input:
        f"data/{geo_name}/output/daily/meteorology__gridmet__{shapefiles}_daily__{{year}}.parquet",
    output:
        f"data/{geo_name}/output/yearly/meteorology__gridmet__{shapefiles}_yearly__{{year}}.parquet",
    log:
        f"logs/{geo_name}/format_gridmet_{{year}}.log",
    shell:
        """
        python src/get_yearly.py year={wildcards.year}
        """