import os
import wget
import hydra
import logging
from pathlib import Path

try:
    from src.gridmet_paths import raw_gridmet_path
except ModuleNotFoundError:
    from gridmet_paths import raw_gridmet_path

LOGGER = logging.getLogger(__name__)


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """
    Download GridMET rasters for a given year.
    """
    desc = cfg.gridmet.variable_key[cfg.var]
    LOGGER.info(f"Downloading GridMET for year={cfg.year} var={desc} ({cfg.var})")

    # make url and target file
    url = cfg.gridmet.url + f"{cfg.var}_{cfg.year}.nc"
    target_file = raw_gridmet_path(cfg.datapaths, cfg.polygon_name, cfg.var, cfg.year)
    Path(target_file).parent.mkdir(parents=True, exist_ok=True)

    # download file with wget
    LOGGER.info(f"Downloading...")
    wget.download(url, target_file)
    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
