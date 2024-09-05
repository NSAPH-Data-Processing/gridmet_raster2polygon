import logging
import os
import hydra
from omegaconf import DictConfig

LOGGER = logging.getLogger(__name__)

def create_subfolders_and_links(datapath, subfolder_dict, base_path="data"):
    """
    Recursively create subfolders and symbolic links.
    """
    for subfolder_name, subfolder_link in subfolder_dict.items():
        subfolder_path = os.path.join(base_path, datapath, subfolder_name)

        if isinstance(subfolder_link, DictConfig):
            # Recursive call for nested subfolders
            create_subfolders_and_links(subfolder_name, subfolder_link, os.path.join(base_path, datapath))
        else:
            if os.path.exists(subfolder_path):
                LOGGER.info(f"Subfolder {subfolder_path} already exists.")
                continue
            if subfolder_link is not None:
                #convert relative path to absolute path
                subfolder_link = os.path.abspath(subfolder_link)
                os.symlink(subfolder_link, subfolder_path)
                LOGGER.info(f"Created symlink {subfolder_path} -> {subfolder_link}")
            else:
                os.makedirs(subfolder_path, exist_ok=True)
                LOGGER.info(f"Created subfolder {subfolder_path}")

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """Create data subfolders and symbolic links as indicated in config file."""
    for datapath, subfolder_dict in cfg.datapaths.items():
        create_subfolders_and_links(datapath, subfolder_dict)

if __name__ == "__main__":
    main()
