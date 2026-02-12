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
from pathlib import Path
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s] - %(message)s')
LOGGER = logging.getLogger(__name__)


def download_file(url, output_path, file_label="file"):
    """Download a file from a URL with progress bar."""
    LOGGER.info(f"Downloading {file_label} from {url}")
    
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=file_label) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    
    LOGGER.info(f"Downloaded to: {output_path}")
    return output_path


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """
    Download population count data from Harvard Dataverse.
    
    Files are saved to the configured population data directory.
    """
    
    population_cfg = cfg.population
    population_type = cfg.get('population_type', population_cfg.default_type)
    year = cfg.get('year', cfg.year)
    
    # Get configuration for the selected population type
    pop_config = population_cfg[population_type]
    
    LOGGER.info(f"Downloading population {population_type} data for year {year}")
    LOGGER.info(f"DOI: {pop_config.doi}")
    
    # Construct output path
    output_dir = Path(population_cfg.data_dir) / population_type
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if we have a file mapping for this year
    if 'file_map' in pop_config and year in pop_config.file_map:
        file_info = pop_config.file_map[year]
        filename = file_info['filename']
        file_id = file_info.get('file_id')
        
        output_path = output_dir / filename
        
        # Skip if already exists
        if output_path.exists():
            LOGGER.info(f"File already exists: {output_path}")
            return
        
        # Construct download URL
        if file_id:
            # Direct file download from Dataverse
            download_url = f"https://dataverse.harvard.edu/api/access/datafile/{file_id}"
        elif 'url' in file_info:
            download_url = file_info['url']
        else:
            LOGGER.error(f"No download URL or file_id found for year {year}")
            return
        
        download_file(download_url, str(output_path), f"Population {population_type} {year}")
        
    else:
        LOGGER.warning(f"No file mapping found for year {year}")
        LOGGER.warning(f"Please add file information to conf/population.yaml")
        LOGGER.info(f"Visit {pop_config.doi} to find available files")


if __name__ == "__main__":
    main()
