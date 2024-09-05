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

    # download directory
    target_dir = f"data/input/gridmet_rasters"
    os.makedirs(target_dir, exist_ok=True)  # create directory if it doesn't exist

    # make url and target file
    url = cfg.gridmet.url + f"{cfg.var}_{cfg.year}.nc"
    target_file = f"{target_dir}/{cfg.var}_{cfg.year}.nc"

    # skip if file already exists
    if os.path.exists(target_file):
        LOGGER.info(f"File exists. Skipping.")
        return

    # download file with wget
    LOGGER.info(f"Downloading...")
    wget.download(url, target_file)
    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
