import logging
import os
import hydra
from omegaconf import DictConfig

LOGGER = logging.getLogger(__name__)

def create_subfolders_and_links(datapath="data", folder_dict=None):
    """
    Recursively create subfolders and symbolic links.
    """
    if os.path.exists(datapath):
        LOGGER.info(f"Folder {datapath} already exists.")
    else:
        os.mkdir(datapath)
        LOGGER.info(f"Created data path {datapath}")

    if isinstance(folder_dict, DictConfig):
        for path, dict in folder_dict.items():
            # Recursive call for nested subfolders
            create_subfolders_and_links(os.path.join(datapath, path), dict)
    elif folder_dict is None:
        LOGGER.info(f"End of recursive branch")
    else:
        #convert relative path to absolute path
        folder_link = os.path.abspath(folder_dict)
        os.symlink(folder_dict, datapath)
        LOGGER.info(f"Created symlink {datapath} -> {folder_link}")

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """Create data subfolders and symbolic links as indicated in config file."""
    create_subfolders_and_links(folder_dict=cfg.datapaths)

if __name__ == "__main__":
    main()

