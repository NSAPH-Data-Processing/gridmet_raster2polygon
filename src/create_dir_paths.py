import logging
import os
import hydra
from omegaconf import DictConfig

LOGGER = logging.getLogger(__name__)

def create_subfolders_and_links(datapath="data", folder_dict=None):
    """
    Recursively create subfolders and symbolic links.
    """
    if not os.path.exists(datapath):
        LOGGER.info(f"Error: {datapath} does not exists.")
        return
    if isinstance(folder_dict, DictConfig):
        for path, subfolder_dict in folder_dict.items():
            sub_datapath = os.path.join(datapath, path)
            if isinstance(subfolder_dict, str):
                # Create symbolic link
                if os.path.exists(sub_datapath):
                    LOGGER.info(f"Symbolic link to {sub_datapath} already exists")
                else:
                    os.symlink(os.path.abspath(subfolder_dict), sub_datapath)
                    LOGGER.info(f"Created symlink {sub_datapath} -> {subfolder_dict}")
            else:
                # Create subfolder
                if os.path.exists(sub_datapath):
                    LOGGER.info(f"Path {sub_datapath} already exists")
                else:
                    os.mkdir(sub_datapath)
                    LOGGER.info(f"Created data path {sub_datapath}")
                if subfolder_dict is not None:
                    # Recursive call for nested subfolders
                    create_subfolders_and_links(sub_datapath, subfolder_dict)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """Create data subfolders and symbolic links as indicated in config file."""
    create_subfolders_and_links(folder_dict=cfg.datapaths)

if __name__ == "__main__":
    main()

