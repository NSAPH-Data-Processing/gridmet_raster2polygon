"""
Download population data from Harvard Dataverse.

This script downloads population count data from Harvard Dataverse
to be used for population-weighted aggregation of gridMET variables.

Data source:
- Population Count: https://doi.org/10.7910/DVN/C0LVYI

Usage:
    python src/download_population.py year=2010
"""

import os
import logging
import hydra
import requests
import zipfile
from pathlib import Path
from pyDataverse.api import NativeApi

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s] - %(message)s')
LOGGER = logging.getLogger(__name__)





@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """
    Download population count data from Harvard Dataverse.

    If an exact match for the requested year is not found in the file_map,
    falls back to the nearest available year that precedes the requested year.
    The output .tif is always saved using the requested year in the filename:
        world_population__sedac__world_yearly__{year}.tif

    Files are saved to the configured population data directory.
    """

    population_cfg = cfg.population
    year = cfg.get('year', cfg.year)

    pop_config = population_cfg.count

    # Derive data_root: consolidated configs (cannon_core, cannon_popweighted) nest data
    # under base_path/{polygon_name}; single-geo configs use base_path directly.
    base_path = getattr(cfg.datapaths, 'base_path', None)

    raw_dir = f"{base_path}/population/input/raw"
    output_dir = f"{base_path}/population/output"
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Resolve source year: exact match or nearest preceding year
    available_years = sorted(pop_config.file_map.keys())
    if year in pop_config.file_map:
        source_year = year
    else:
        preceding = [y for y in available_years if y < year]
        if not preceding:
            raise ValueError(
                f"Requested year {year} precedes all available population years: {available_years}. "
                f"Cannot find a valid preceding file."
            )
        source_year = max(preceding)
        LOGGER.info(
            f"No population data for year {year}; "
            f"falling back to nearest preceding year {source_year}"
        )

    file_info = pop_config.file_map[source_year]
    zip_filename = file_info['filename']
    tif_path_in_zip = file_info['files'][0]  # path of .tif inside the zip

    # Output .tif uses the REQUESTED year so each year has a unique file
    output_path = Path(output_dir) / f"world_population__sedac__world_yearly__{year}.tif"

    if output_path.exists():
        LOGGER.info(f"File already exists: {output_path}")
        return

    LOGGER.info(f"Downloading population count for year {year} (source year: {source_year})")
    LOGGER.info(f"DOI: {pop_config.doi}")

    # Connect to Dataverse
    baseurl = "https://dataverse.harvard.edu"
    api = NativeApi(baseurl)

    dataset = api.get_dataset(pop_config.doi)
    files_list = dataset.json()["data"]["latestVersion"]["files"]
    file2id = {f["dataFile"]["filename"]: f["dataFile"]["id"] for f in files_list}

    if zip_filename not in file2id:
        raise FileNotFoundError(
            f"File '{zip_filename}' not found in Dataverse dataset. "
            f"Available files: {list(file2id.keys())}"
        )

    # Cache the zip in the raw input directory
    zip_path = Path(raw_dir) / zip_filename
    if not zip_path.exists():
        LOGGER.info(f"Downloading {zip_filename}...")
        file_id = file2id[zip_filename]
        download_url = f"{baseurl}/api/access/datafile/{file_id}"
        response = requests.get(download_url)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            f.write(response.content)
        LOGGER.info(f"Zip cached at: {zip_path}")
    else:
        LOGGER.info(f"Using cached zip: {zip_path}")

    # Extract the .tif and save with the requested-year filename
    LOGGER.info(f"Extracting {tif_path_in_zip}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        names = zip_ref.namelist()
        if tif_path_in_zip not in names:
            tif_candidates = [n for n in names if n.endswith('.tif')]
            if not tif_candidates:
                raise FileNotFoundError(f"No .tif found in {zip_path}. Contents: {names}")
            tif_path_in_zip = tif_candidates[0]
            LOGGER.warning(f"Configured path not found in zip; using '{tif_path_in_zip}' instead")
        with zip_ref.open(tif_path_in_zip) as tif_src:
            with open(output_path, 'wb') as tif_dst:
                tif_dst.write(tif_src.read())

    LOGGER.info(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
