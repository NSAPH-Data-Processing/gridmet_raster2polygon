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
from pyDataverse.api import DataAccessApi, NativeApi

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s] - %(message)s')
LOGGER = logging.getLogger(__name__)





@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """
    Download population count data from Harvard Dataverse.
    
    Files are saved to the configured population data directory.
    """
    
    population_cfg = cfg.population
    year = cfg.get('year', cfg.year)
    
    # Always use population count
    pop_config = population_cfg.count
    
    LOGGER.info(f"Downloading population count data for year {year}")
    LOGGER.info(f"DOI: {pop_config.doi}")
    
    # Connect to Dataverse
    baseurl = "https://dataverse.harvard.edu"
    api = NativeApi(baseurl)
    data_api = DataAccessApi(baseurl)
    
    # Get dataset information
    dataset = api.get_dataset(pop_config.doi)
    files_list = dataset.json()["data"]["latestVersion"]["files"]
    
    # Create mapping of filename to file ID
    file2id = {f["dataFile"]["filename"]: f["dataFile"]["id"] for f in files_list}
    
    # Check if we have a file mapping for this year
    if 'file_map' in pop_config and year in pop_config.file_map:
        file_info = pop_config.file_map[year]
        target_filename = file_info['filename']
        
        # Construct output path (always use 'count' subdirectory)
        output_dir = Path(population_cfg.data_dir) / 'count'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / target_filename
        
        # Skip if already exists
        if output_path.exists():
            LOGGER.info(f"File already exists: {output_path}")
            return
        
        # Find file in Dataverse
        if target_filename not in file2id:
            available_files = list(file2id.keys())
            LOGGER.error(f"File {target_filename} not found in Dataverse dataset")
            LOGGER.error(f"Available files: {available_files}")
            return
        
        # Download file using direct URL
        LOGGER.info(f"Downloading {target_filename}...")
        file_id = file2id[target_filename]
        download_url = f"{baseurl}/api/access/datafile/{file_id}"
        
        response = requests.get(download_url)
        response.raise_for_status()
        
        # Save file
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        LOGGER.info(f"Downloaded to: {output_path}")
        
        # Extract if it's a zip file
        if target_filename.endswith('.zip'):
            extract_dir = output_dir / target_filename.replace('.zip', '')
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            LOGGER.info(f"Extracting {target_filename} to {extract_dir}...")
            with zipfile.ZipFile(output_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            LOGGER.info(f"Extraction complete. Files extracted to: {extract_dir}")
        
    else:
        LOGGER.warning(f"No file mapping found for year {year}")
        LOGGER.warning(f"Please add file information to conf/population.yaml")
        LOGGER.info(f"Visit {pop_config.doi} to find available files")


if __name__ == "__main__":
    main()
