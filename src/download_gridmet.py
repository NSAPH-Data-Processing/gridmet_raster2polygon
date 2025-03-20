import os
import wget
import hydra
import logging

LOGGER = logging.getLogger(__name__)


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """
    Download GridMET rasters for a given year.
    """
    # year
    desc = cfg.gridmet.variable_key[cfg.var]
    LOGGER.info(f"Downloading GridMET for year={cfg.year} var={desc} ({cfg.var})")

    geo_name = cfg.datapaths.name
    # download directory
    target_dir = f"data/{geo_name}/input/raw"

    # make url and target file
    url = cfg.gridmet.url + f"{cfg.var}_{cfg.year}.nc"
    target_file = f"{target_dir}/{cfg.var}_{cfg.year}.nc"

    # download file with wget
    LOGGER.info(f"Downloading...")
    wget.download(url, target_file)
    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
