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
    desc = cfg.gridmet.variable_key[cfg.var]
    LOGGER.info(f"Downloading GridMET for year={cfg.year} var={desc} ({cfg.var})")

    base_path = getattr(cfg.datapaths, 'base_path', None)
    dirs_cfg = cfg.datapaths.dirs
    if hasattr(dirs_cfg, cfg.polygon_name):
        data_root = f"{base_path}/{cfg.polygon_name}"
    else:
        data_root = base_path or f"data/{cfg.polygon_name}"
    # download directory
    target_dir = f"{data_root}/input/raw"

    # make url and target file
    url = cfg.gridmet.url + f"{cfg.var}_{cfg.year}.nc"
    target_file = f"{target_dir}/{cfg.var}_{cfg.year}.nc"

    # download file with wget
    LOGGER.info(f"Downloading...")
    wget.download(url, target_file)
    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
