import logging
import os
import hydra
from omegaconf import DictConfig

LOGGER = logging.getLogger(__name__)

def create_subfolders_and_links(datapath="data", folder_dict=None):
    """
    Recursively create subfolders and symbolic links, organizing by geography name.
    Logs errors for existing symlinks pointing to incorrect locations.
    """
    if not os.path.exists(datapath):
        LOGGER.info(f"Error: {datapath} does not exist.")
        return

    if isinstance(folder_dict, DictConfig):
        geography_name = folder_dict.get("name", None)
        if geography_name is None:
            geography_name = ""

        # Define base directories for the geography
        input_path = os.path.join(datapath, "input", geography_name)
        intermediate_path = os.path.join(datapath, "intermediate", geography_name)
        output_daily_path = os.path.join(datapath, "output", geography_name, "daily")
        output_yearly_path = os.path.join(datapath, "output", geography_name, "yearly")

        # Ensure base directories exist
        for path in [intermediate_path, output_daily_path, output_yearly_path]:
            os.makedirs(path, exist_ok=True)
            LOGGER.info(f"Created or verified existence of {path}")

        # Process remaining folder_dict entries
        for path, subfolder_dict in folder_dict.items():
            if path == "name":  # Skip the name key
                continue
            
            # Default placement in intermediate unless explicitly categorized
            sub_datapath = os.path.join(intermediate_path, path)
            if path in ["daily", "yearly"]:
                sub_datapath = os.path.join(datapath, "output", geography_name, path)

            if isinstance(subfolder_dict, str):
                # Handle symbolic links
                if os.path.islink(sub_datapath):
                    link_target = os.readlink(sub_datapath)
                    if os.path.abspath(link_target) == os.path.abspath(subfolder_dict):
                        LOGGER.info(f"Valid symlink already exists: {sub_datapath} -> {subfolder_dict}")
                    else:
                        LOGGER.info(f"Error: {sub_datapath} is a symlink to {link_target}, not {subfolder_dict}")
                        return
                elif os.path.exists(sub_datapath):
                    LOGGER.info(f"Error: Path {sub_datapath} already exists and is not a symlink")
                    return
                else:
                    os.makedirs(os.path.abspath(subfolder_dict), exist_ok=True)
                    os.symlink(os.path.abspath(subfolder_dict), sub_datapath)
                    LOGGER.info(f"Created symlink {sub_datapath} -> {subfolder_dict}")

            elif isinstance(subfolder_dict, dict):
                # Create normal directories
                os.makedirs(sub_datapath, exist_ok=True)
                LOGGER.info(f"Created data path {sub_datapath}")
                create_subfolders_and_links(sub_datapath, subfolder_dict)  # Recursively process nested subfolders


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """Create data subfolders and symbolic links as indicated in config file."""
    create_subfolders_and_links(folder_dict=cfg.datapaths)

if __name__ == "__main__":
    main()

