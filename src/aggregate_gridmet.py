import pickle
from tqdm import tqdm
import xarray
import rasterio
import pandas as pd
import geopandas as gpd
import numpy as np
import hydra
import logging
import matplotlib.pyplot as plt
from scipy.ndimage import zoom

from hydra.core.hydra_config import HydraConfig
from utils.faster_zonal_stats import polygon_to_raster_cells


# configure logger to print at info level
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def available_shapefile_year(year, shapefile_years_list: list):
    """
    Given a list of shapefile years,
    return the latest year in the shapefile_years_list that is less than or equal to the given year
    """
    for shapefile_year in sorted(shapefile_years_list, reverse=True):
        if year >= shapefile_year:
            return shapefile_year

    return min(
        shapefile_years_list
    )  # Returns the last element if year is greater than the last element


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    # get aggregation defaults
    desc = cfg.gridmet.variable_key[cfg.var]
    LOGGER.info(f"Aggregating year={cfg.year} for var={desc} ({cfg.var})")

    # load shapefile
    LOGGER.info("Loading shapefile...")
    # use previously available shapefile
    shapefile_years_list = list(cfg.shapefiles.keys())
    shapefile_year = available_shapefile_year(cfg.year, shapefile_years_list)

    shape_path = f"data/input/shapefiles/shapefile_{cfg.polygon_name}_{shapefile_year}/shapefile.pkl"
    with open(shape_path, "rb") as f:
        polygon = pickle.load(f)
    polygon_ids = polygon[cfg.shapefiles[shapefile_year].idvar].values

    raster_path = f"data/input/gridmet_rasters/{cfg.var}_{cfg.year}.nc"
    ds = xarray.open_dataset(raster_path)
    layer_name = list(ds.keys())[0]
    layer = ds[layer_name]

    # langitued/latitude info used for affine transform
    lon = layer.lon.values
    lat = layer.lat.values
    dlon = (lon[1] - lon[0]) / cfg.downscaling_factor
    dlat = (lat[0] - lat[1]) / cfg.downscaling_factor

    # first time computing mapping from vector geometries to raster cells
    LOGGER.info("Mapping polygons to raster cells...")

    x = layer.values[0].astype(np.float32)  # 32-bit improves memory after downscaling

    if cfg.downscaling_factor > 1:
        x = zoom(x, cfg.downscaling_factor, order=1)
        LOGGER.info(f"(downscaled by factor {cfg.downscaling_factor})")

    transform = rasterio.transform.from_origin(lon[0], lat[0], dlon, dlat)
    poly2cells = polygon_to_raster_cells(
        polygon.geometry.values,
        x,
        affine=transform,
        all_touched=True,
        nodata=np.nan,
        verbose=cfg.show_progress,
    )

    df_chunks = []  # collects the results for each day

    LOGGER.info("Computing zonal stats for each day...")
    for i, day in tqdm(enumerate(layer.day.values), disable=(not cfg.show_progress)):
        stats = []
        x = layer.sel(day=day).values.astype(np.float32)  # reference array
        if cfg.downscaling_factor > 1:
            x = zoom(x, cfg.downscaling_factor, order=1)

        for indices in poly2cells:
            if len(indices[0]) == 0:
                # no cells found for this polygon
                stats.append(np.nan)
            else:
                cells = x[indices]
                if sum(~np.isnan(cells)) == 0:
                    # no valid cells found for this polygon
                    stats.append(np.nan)
                    continue
                else:
                    # compute mean of valid cells
                    stats.append(np.nanmean(cells))

        df = pd.DataFrame(
            {"day": day, cfg.var: stats},
            index=pd.Index(polygon_ids, name=cfg.polygon_name),
        )

        df_chunks.append(df)

        if i == 0 and cfg.plot_output:
            # convert to geopandas for image
            gdf = gpd.GeoDataFrame(
                df, geometry=polygon.geometry.values, crs=polygon.crs
            )
            logging_dir = HydraConfig.get().runtime.output_dir
            png_path = f"{logging_dir}/{cfg.var}_{cfg.polygon_name}_{cfg.year}.png"
            gdf.plot(column=cfg.var, legend=True)
            plt.savefig(png_path)
            gdf["dummy"] = 1
            gdf.plot(column="dummy", legend=False)
            png_path = f"{logging_dir}/dummy_{cfg.polygon_name}_{cfg.year}.png"
            # plot in continental us bounds
            plt.xlim(-125, -65)
            plt.ylim(25, 50)
            # save with higher resolution
            plt.savefig(png_path, dpi=300)
            LOGGER.info("Plotted result.")

    # concatenate all the days
    df = pd.concat(df_chunks)

    # == save output file
    output_filename = f"{cfg.var}_{cfg.year}_{cfg.polygon_name}.parquet"
    output_path = f"data/output/gridmet_raster2polygon/{output_filename}"
    df.to_parquet(output_path)


if __name__ == "__main__":
    main()
