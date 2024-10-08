import logging
import os
import zipfile
import hydra
import wget
import geopandas as gpd
import pickle


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    url = cfg.shapefiles[cfg.shapefile_year].url

    tgt = f"data/input/shapefiles/shapefile_{cfg.polygon_name}_{cfg.shapefile_year}"

    tgtdir = os.path.dirname(tgt)
    tgtfile = os.path.basename(tgt)

    tgt = f"{tgtdir}/{tgtfile}"
    logging.info(f"Downloading {url}")
    wget.download(url, f"{tgt}.zip")
    logging.info("Done.")

    # unzip with unzip library
    with zipfile.ZipFile(f"{tgt}.zip", "r") as zip_ref:
        zip_ref.extractall(tgt)
    logging.info(f"Unzipped {tgt} with files:\n {os.listdir(tgt)}")

    # remove dirty zip file
    os.remove(f"{tgt}.zip")
    logging.info(f"Removed {tgt}.zip")

    logging.info(f"Rename files to shapefile.*")
    files = os.listdir(tgt)
    for f in files:
        _, ext = os.path.splitext(f)
        os.rename(f"{tgt}/{f}", f"{tgt}/shapefile{ext}")
    logging.info(f"Done.")

    # read the shapefile
    logging.info(f"Reading shapefile...")
    shp = gpd.read_file(f"{tgt}/shapefile.shp")
    shp.geometry = shp.geometry.simplify(0.001, preserve_topology=True)

    # save the shapefile
    logging.info(f"Saving shapefile (pickle)...")
    with open(f"{tgt}/shapefile.pkl", "wb") as f:
        pickle.dump(shp, f, protocol=pickle.HIGHEST_PROTOCOL)


if __name__ == "__main__":
    main()
