import os
import hydra
from src.gridmet_paths import (
    final_output_path,
    intermediate_path,
    population_output_path,
    raw_gridmet_path,
)

conda: "requirements.yaml"
configfile: "conf/snakemake.yaml"


envvars:
    "PYTHONPATH",  # this indicates that the PYTHONPATH must be set, always done in docker


years = list(range(config["years"][0], config["years"][1] + 1))
vars = config["gridmet_vars"]
shapefiles = config["shapefiles"]
datapaths = config["datapaths"]  # cannon_core or cannon_popweighted
run_seasonal = config.get("run_seasonal", False)
seasonal_datapaths = "cannon_seasonal"
seasonal_source_datapaths = "cannon_core"

# == Load config as hydra with defaults ==
population_weighting = datapaths == "cannon_popweighted"
overrides = [
    f"datapaths={datapaths}",
    f"shapefiles={shapefiles}",
    f"population.weighting.enabled={str(population_weighting).lower()}",
]
with hydra.initialize(version_base=None, config_path="conf"):
    hydra_cfg = hydra.compose(config_name="config", overrides=overrides)
    seasonal_cfg = hydra.compose(
        config_name="config",
        overrides=[
            f"datapaths={seasonal_datapaths}",
            f"shapefiles={shapefiles}",
            "population.weighting.enabled=false",
        ],
    )
    seasonal_source_cfg = hydra.compose(
        config_name="config",
        overrides=[
            f"datapaths={seasonal_source_datapaths}",
            f"shapefiles={shapefiles}",
            "population.weighting.enabled=false",
        ],
    )

raw_gridmet_pattern = raw_gridmet_path(hydra_cfg.datapaths, shapefiles, "{var}", "{year}")
intermediate_pattern = intermediate_path(hydra_cfg.datapaths, shapefiles, "{var}", "{year}")
daily_output_pattern = final_output_path(hydra_cfg.datapaths, shapefiles, "daily", "{year}")
yearly_output_pattern = final_output_path(hydra_cfg.datapaths, shapefiles, "yearly", "{year}")
population_output_pattern = population_output_path(hydra_cfg.datapaths, "{year}")
seasonal_daily_input_pattern = final_output_path(
    seasonal_source_cfg.datapaths,
    shapefiles,
    "daily",
    "{year}",
)
seasonal_yearly_output_pattern = final_output_path(
    seasonal_cfg.datapaths,
    shapefiles,
    "yearly",
    "{year}",
)

# needed to import modules from utils/ when running aggregate_gridmet.py
if "PYTHONPATH" in os.environ:
    os.environ["PYTHONPATH"] += ":."

print(f"datapaths resolved to: {datapaths}")
print(f"daily output pattern resolved to: {daily_output_pattern}")
print(f"yearly output pattern resolved to: {yearly_output_pattern}")

all_outputs = expand(
    yearly_output_pattern,
    year=years,
)

if run_seasonal:
    all_outputs += expand(
        seasonal_yearly_output_pattern,
        year=years,
    )

# == Define rules ==
rule all:
    input:
        all_outputs,

rule download_gridmet:
    output:
        raw_gridmet_pattern,
    log:
        err="logs/download_gridmet_{var}_{year}.log",
    shell:
        "python src/download_gridmet.py year={wildcards.year} var={wildcards.var} datapaths={datapaths} shapefiles={shapefiles} 2> {log.err}"

rule download_population:
    output:
        population_output_pattern,
    log:
        err="logs/download_population_{year}.log",
    shell:
        "python src/download_population.py year={wildcards.year} datapaths={datapaths} shapefiles={shapefiles} 2> {log.err}"

rule aggregate_gridmet:
    input:
        gridmet=raw_gridmet_pattern,
        population=population_output_pattern if hydra_cfg.population.weighting.enabled else [],
    output:
        intermediate_pattern,
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
            intermediate_pattern,
            var=vars, 
            year="{year}"
        ),
    output:
        daily_output_pattern,
    log:
        f"logs/{shapefiles}/format_gridmet_{{year}}.log",
    shell:
        """
        python src/format_gridmet.py year={wildcards.year} datapaths={datapaths} shapefiles={shapefiles} &> {log}
        """

rule get_yearly:
    input:
        daily_output_pattern,
    output:
        yearly_output_pattern,
    log:
        f"logs/{shapefiles}/get_yearly_{{year}}.log",
    shell:
        """
        python src/get_yearly.py year={wildcards.year} datapaths={datapaths} shapefiles={shapefiles} &> {log}
        """
rule get_seasonal:
    input:
        seasonal_daily_input_pattern,
    output:
        seasonal_yearly_output_pattern,
    log:
        f"logs/{shapefiles}/get_seasonal_{{year}}.log",
    shell:
        """
        python src/seasonal_vars.py year={wildcards.year} datapaths={seasonal_datapaths} shapefiles={shapefiles} +seasonal_source_datapaths={seasonal_source_datapaths} &> {log}
        """
