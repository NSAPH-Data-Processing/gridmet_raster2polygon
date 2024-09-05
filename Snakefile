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

# == Load config as hydra with defaults ==
overrides = [f"shapefiles={shapefiles}"]
with hydra.initialize(version_base=None, config_path="conf"):
    hydra_cfg = hydra.compose(config_name="config", overrides=overrides)

# needed to import modules from utils/ when running aggregate_gridmet.py
if "PYTHONPATH" in os.environ:
    os.environ["PYTHONPATH"] += ":."


## == Contructs the input polygon for a given year
def get_shapefile_input(wildcards):
    shapefile_years_list = list(hydra_cfg.shapefiles.keys())
    shapefile_year = available_shapefile_year(int(wildcards.year), shapefile_years_list)
    return (
        f"data/input/shapefiles/shapefile_{shapefiles}_{shapefile_year}/shapefile.pkl"
    )


# == Define rules ==
rule all:
    input:
        expand(
            f"data/output/gridmet_raster2polygon/{{var}}_{{year}}_{shapefiles}.parquet",
            year=years,
            var=vars,
        ),


rule download_shapefiles:
    output:
        f"data/input/shapefiles/shapefile_{shapefiles}_{{shapefile_year}}/shapefile.pkl",
    shell:
        f"""
        python src/download_shapefile.py shapefiles={shapefiles} \
            shapefile_year={{wildcards.shapefile_year}}
        """


rule download_gridmet:
    output:
        "data/input/gridmet_rasters/{var}_{year}.nc",
    log:
        err="logs/download_gridmet_{var}_{year}.log",
    shell:
        "python utils/download_gridmet.py year={wildcards.year} var={wildcards.var} 2> {log.err}"





rule aggregate_gridmet:
    input:
        get_shapefile_input,
        "data/input/gridmet_rasters/{var}_{year}.nc",
    output:
        f"data/output/gridmet_raster2polygon/{{var}}_{{year}}_{shapefiles}.parquet",
    log:
        f"logs/aggregate_gridmet_{{var}}_{{year}}_{shapefiles}.log",
    params:
        overrides=" ".join(overrides),  # pass hydra overrides (here just shapefiles)
    shell:
        """
        python src/aggregate_gridmet.py year={wildcards.year} var={wildcards.var} {params.overrides} \
             &> {log}
        """
