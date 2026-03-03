from tqdm import tqdm
import xarray
import rasterio
import pandas as pd
import geopandas as gpd
import numpy as np
import hydra
import logging
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.ndimage import zoom
from rasterio.warp import reproject, Resampling 
from hydra.core.hydra_config import HydraConfig
import sys
sys.path.append('./')
from utils.faster_zonal_stats import polygon_to_raster_cells, compute_zonal_stats


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

    return min(shapefile_years_list)


# ===========================
# Grid alignment helpers
# ===========================

def _same_grid(src_transform, src_shape, dst_transform, dst_shape, tol=1e-12):
    """
    Determine if two rasters represent the *same grid*.

    We check:
    - array shape: (height, width)
    - affine transform: six parameters (a, b, c, d, e, f)

    Why this matters:
    - Population weighting requires weights and values to be aligned cell-by-cell.
    - If grids differ, we must reproject/warp population onto the gridMET grid.

    tol:
    - floating-point transforms can have tiny numeric differences; we allow a tolerance.
    """
    if src_shape != dst_shape:
        return False

    a = src_transform
    b = dst_transform
    
    # Compare each affine parameter within tolerance.
    # a.a and a.e represent pixel sizes (x and y); a.c and a.f represent origin offsets.
    return (
        abs(a.a - b.a) < tol and
        abs(a.b - b.b) < tol and
        abs(a.c - b.c) < tol and
        abs(a.d - b.d) < tol and
        abs(a.e - b.e) < tol and
        abs(a.f - b.f) < tol
    )


def align_population_to_gridmet(pop_path: str, gridmet_shape: tuple,gridmet_transform, gridmet_crs="EPSG:4326"):
    """
    Read population GeoTIFF (counts per pixel) and realign to exactly match the gridMET grid
    (gridmet_shape + gridmet_transform). Uses nearest-neighbor resampling.

    Returns
    -------
    np.ndarray (float32)
        Population counts aligned to gridMET grid (same shape as gridMET).
    """
    with rasterio.open(pop_path) as src:
        pop = src.read(1).astype(np.float32)

        # Replace nodata/NaN with 0 people
        if src.nodata is not None:
            pop = np.where(pop == src.nodata, 0.0, pop)
        pop = np.where(np.isfinite(pop), pop, 0.0)
        pop[pop < 0] = 0.0

        src_transform = src.transform
        src_shape = (src.height, src.width)

        # If CRS missing, assume EPSG:4326
        src_crs = src.crs if src.crs is not None else gridmet_crs

        # Check if population grid matches gridMET grid exactly (same shape + transform)
        if _same_grid(src_transform, src_shape, gridmet_transform, gridmet_shape):
            LOGGER.info("Population grid matches gridMET grid exactly; no warp needed.")
            return pop

        LOGGER.info("Warping population to gridMET grid (same resolution; snapping origin/extent).")

        dst = np.zeros(gridmet_shape, dtype=np.float32)

        reproject(
            source=pop,
            destination=dst,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=gridmet_transform,
            dst_crs=gridmet_crs,
            resampling=Resampling.nearest, 
            src_nodata=0.0,
            dst_nodata=0.0,
        )

        dst = np.where(np.isfinite(dst), dst, 0.0)
        dst[dst < 0] = 0.0
        return dst


def plot_population_qc(df_weighted, df_unweighted, polygon, cfg, logging_dir):
    """
    Generate QC plots comparing population-weighted vs unweighted aggregation.

    Produces a multi-panel figure:
      1. Time series of daily spatial-mean (weighted vs unweighted)
      2. Scatter plot of weighted vs unweighted polygon values
      3. Histogram of per-polygon differences (weighted - unweighted)
      4. Side-by-side spatial maps for the first available day

    Parameters
    ----------
    df_weighted : pd.DataFrame
        Aggregated data with population weighting (columns: 'day', var).
    df_unweighted : pd.DataFrame
        Aggregated data without population weighting (same schema).
    polygon : gpd.GeoDataFrame
        Shapefile geometries used for spatial maps.
    cfg : OmegaConf
        Hydra configuration object.
    logging_dir : str
        Directory to save QC plots.
    """
    var = cfg.var
    year = cfg.year
    polygon_name = cfg.polygon_name
    desc = cfg.gridmet.variable_key[var]

    # --- Panel 1: daily spatial-mean time series ---
    daily_w = df_weighted.groupby("day")[var].mean()
    daily_u = df_unweighted.groupby("day")[var].mean()

    fig = plt.figure(figsize=(16, 14))
    gs = gridspec.GridSpec(2, 2, hspace=0.35, wspace=0.3)

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(daily_u.index, daily_u.values, label="Unweighted", alpha=0.8, linewidth=1)
    ax1.plot(daily_w.index, daily_w.values, label="Pop-weighted", alpha=0.8, linewidth=1)
    ax1.set_xlabel("Day")
    ax1.set_ylabel(f"{desc} ({var})")
    ax1.set_title(f"Daily Mean Across All {polygon_name}s ({year})")
    ax1.legend()
    ax1.tick_params(axis="x", rotation=45)

    # --- Panel 2: scatter – weighted vs unweighted per polygon-day ---
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.scatter(
        df_unweighted[var].values,
        df_weighted[var].values,
        s=2, alpha=0.3, edgecolors="none",
    )
    lims = [
        min(df_unweighted[var].min(), df_weighted[var].min()),
        max(df_unweighted[var].max(), df_weighted[var].max()),
    ]
    ax2.plot(lims, lims, "r--", linewidth=0.8, label="1:1 line")
    ax2.set_xlabel(f"Unweighted {var}")
    ax2.set_ylabel(f"Pop-weighted {var}")
    ax2.set_title("Weighted vs Unweighted (all polygon-days)")
    ax2.legend(loc="upper left")

    # --- Panel 3: histogram of differences ---
    diff = df_weighted[var].values - df_unweighted[var].values
    diff = diff[np.isfinite(diff)]
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.hist(diff, bins=60, edgecolor="black", linewidth=0.3, alpha=0.7)
    ax3.axvline(0, color="red", linestyle="--", linewidth=0.8)
    ax3.set_xlabel(f"Difference (weighted − unweighted)")
    ax3.set_ylabel("Count")
    ax3.set_title(f"Distribution of Differences ({year})")
    median_diff = np.median(diff) if len(diff) > 0 else 0
    ax3.text(
        0.95, 0.95,
        f"median = {median_diff:.4f}\nstd = {np.std(diff):.4f}",
        transform=ax3.transAxes, ha="right", va="top",
        fontsize=9, bbox=dict(facecolor="white", alpha=0.8),
    )

    # --- Panel 4: spatial map of the first day (weighted vs unweighted) ---
    first_day = df_weighted["day"].iloc[0]
    w_first = df_weighted[df_weighted["day"] == first_day][var].values
    u_first = df_unweighted[df_unweighted["day"] == first_day][var].values
    spatial_diff = w_first - u_first

    gdf_diff = gpd.GeoDataFrame(
        {"diff": spatial_diff},
        geometry=polygon.geometry.values,
        crs=polygon.crs,
    )
    ax4 = fig.add_subplot(gs[1, 1])
    vmax = max(abs(np.nanmin(spatial_diff)), abs(np.nanmax(spatial_diff)))
    if vmax == 0:
        vmax = 1
    gdf_diff.plot(
        column="diff", ax=ax4, legend=True, cmap="RdBu_r",
        vmin=-vmax, vmax=vmax,
        legend_kwds={"label": f"Δ {var} (weighted − unweighted)", "shrink": 0.6},
    )
    ax4.set_title(f"Spatial Difference – {first_day.strftime('%Y-%m-%d') if hasattr(first_day, 'strftime') else first_day}")
    ax4.set_xlim(-125, -65)
    ax4.set_ylim(25, 50)
    ax4.set_axis_off()

    fig.suptitle(
        f"Population Weighting QC: {desc} ({var}), {year}, {polygon_name}",
        fontsize=14, fontweight="bold", y=0.98,
    )

    png_path = f"{logging_dir}/pop_qc_{var}_{polygon_name}_{year}.png"
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    LOGGER.info(f"Population QC plot saved to: {png_path}")


def load_population_weights(cfg, gridmet_shape, gridmet_transform, downscaling_factor=1):
    """
    Load population data and align it with gridMET raster grid.

    IMPORTANT:
    - Population weights should be counts-per-pixel.
    - If gridMET is downscaled (e.g., factor=5), do NOT use zoom() on population.
      Instead, warp/snap population GeoTIFF to the exact gridMET grid definition.

    Returns
    -------
    ndarray or None
        Population weights array matching gridMET dimensions, or None if disabled
    """
    if not cfg.population.weighting.enabled:
        return None

    year = cfg.year

    # Derive data_root (same logic as main() and download_population.py)
    base_path = getattr(cfg.datapaths, 'base_path', None)
    dirs_cfg = cfg.datapaths.dirs
    if hasattr(dirs_cfg, cfg.polygon_name):
        data_root = f"{base_path}/{cfg.polygon_name}"
    else:
        data_root = base_path or f"data/{cfg.polygon_name}"

    pop_path = f"{base_path}/population/output/world_population__sedac__world_yearly__{year}.tif"

    try:
        LOGGER.info(f"Loading population count data from: {pop_path}")

        # assume lon/lat grid for gridMET derived from NetCDF coordinates
        gridmet_crs = getattr(cfg, "gridmet_crs", "EPSG:4326")

        # Align population GeoTIFF to the gridMET grid (shape + transform)
        pop_data = align_population_to_gridmet(
            pop_path=pop_path,
            gridmet_shape=gridmet_shape,
            gridmet_transform=gridmet_transform,
            gridmet_crs=gridmet_crs,
        )

        LOGGER.info(f"Population weights aligned (shape: {pop_data.shape})")
        LOGGER.info(f"Total population (aligned): {np.sum(pop_data):,.0f}")

        return pop_data

    except FileNotFoundError:
        LOGGER.error(f"Population file not found: {pop_path}")
        LOGGER.warning("Proceeding with unweighted aggregation")
        return None
    except Exception as e:
        LOGGER.error(f"Error loading population data: {e}")
        LOGGER.warning("Proceeding with unweighted aggregation")
        return None


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    # get aggregation defaults
    desc = cfg.gridmet.variable_key[cfg.var]
    LOGGER.info(f"Aggregating year={cfg.year} for var={desc} ({cfg.var})")

    # Resolve data root path: consolidated configs (cannon_core, cannon_popweighted) nest
    # data under base_path/{polygon_name}; single-geo configs use base_path directly.
    base_path = getattr(cfg.datapaths, 'base_path', None)
    dirs_cfg = cfg.datapaths.dirs
    if hasattr(dirs_cfg, cfg.polygon_name):
        data_root = f"{base_path}/{cfg.polygon_name}"
    else:
        data_root = base_path or f"data/{cfg.polygon_name}"
    LOGGER.info(f"Using data root: {data_root}")

    # load shapefile
    LOGGER.info("Loading shapefile...")
    shapefile_years_list = list(cfg.shapefiles.years)
    shapefile_year = available_shapefile_year(cfg.year, shapefile_years_list)
    shapefile_nm = cfg.shapefiles.prefix + str(shapefile_year)

    shapefile_path = f"{data_root}/input/shapefiles/{shapefile_nm}/{shapefile_nm}.shp"
    polygon = gpd.read_file(shapefile_path)
    polygon_ids = polygon[cfg.shapefiles.idvar].values

    raster_path = f"{data_root}/input/raw/{cfg.var}_{cfg.year}.nc"
    ds = xarray.open_dataset(raster_path)
    layer_name = list(ds.keys())[0]
    layer = ds[layer_name]

    # longitude/latitude info used for affine transform
    lon = layer.lon.values
    lat = layer.lat.values
    dlon = (lon[1] - lon[0]) / cfg.downscaling_factor
    dlat = (lat[0] - lat[1]) / cfg.downscaling_factor

    LOGGER.info("Mapping polygons to raster cells...")

    # reference array to define shape after downscaling
    x = layer.values[0].astype(np.float32)

    if cfg.downscaling_factor > 1:
        x = zoom(x, cfg.downscaling_factor, order=1)
        LOGGER.info(f"(gridMET downscaled by factor {cfg.downscaling_factor})")

    transform = rasterio.transform.from_origin(lon[0], lat[0], dlon, dlat)

    poly2cells = polygon_to_raster_cells(
        polygon.geometry.values,
        x,
        affine=transform,
        all_touched=True,
        nodata=np.nan,
        verbose=cfg.show_progress,
    )

    # Load population weights if enabled (aligned to downscaled grid)
    population_weights = load_population_weights(
        cfg,
        x.shape,
        transform,
        cfg.downscaling_factor
    )

    if population_weights is not None:
        LOGGER.info("Using population-weighted aggregation (count)")
    else:
        LOGGER.info("Using unweighted aggregation (simple mean)")

    df_chunks = []
    df_unweighted_chunks = []  # for QC comparison
    run_pop_qc = getattr(cfg, "plot_population_qc", False) and population_weights is not None

    LOGGER.info("Computing zonal stats for each day...")
    for i, day in tqdm(enumerate(layer.day.values), disable=(not cfg.show_progress)):
        x_day = layer.sel(day=day).values.astype(np.float32)
        if cfg.downscaling_factor > 1:
            x_day = zoom(x_day, cfg.downscaling_factor, order=1)

        stats = compute_zonal_stats(
            x_day,
            poly2cells,
            weights=population_weights,
        )

        df = pd.DataFrame(
            {"day": day, cfg.var: stats},
            index=pd.Index(polygon_ids, name=cfg.polygon_name),
        )
        df_chunks.append(df)

        # Also compute unweighted stats for QC comparison
        if run_pop_qc:
            stats_uw = compute_zonal_stats(x_day, poly2cells, weights=None)
            df_uw = pd.DataFrame(
                {"day": day, cfg.var: stats_uw},
                index=pd.Index(polygon_ids, name=cfg.polygon_name),
            )
            df_unweighted_chunks.append(df_uw)

        if i == 0 and cfg.plot_output:
            gdf = gpd.GeoDataFrame(df, geometry=polygon.geometry.values, crs=polygon.crs)
            logging_dir = HydraConfig.get().runtime.output_dir

            png_path = f"{logging_dir}/{cfg.var}_{cfg.polygon_name}_{cfg.year}.png"
            gdf.plot(column=cfg.var, legend=True)
            plt.savefig(png_path)

            gdf["dummy"] = 1
            gdf.plot(column="dummy", legend=False)
            png_path = f"{logging_dir}/dummy_{cfg.polygon_name}_{cfg.year}.png"

            plt.xlim(-125, -65)
            plt.ylim(25, 50)
            plt.savefig(png_path, dpi=300)
            LOGGER.info("Plotted result.")

    df = pd.concat(df_chunks)

    # Generate population weighting QC plots
    if run_pop_qc:
        df_unweighted = pd.concat(df_unweighted_chunks)
        logging_dir = HydraConfig.get().runtime.output_dir
        plot_population_qc(df, df_unweighted, polygon, cfg, logging_dir)

    output_filename = f"{cfg.var}_{cfg.year}_{cfg.polygon_name}.parquet"
    output_path = f"{data_root}/intermediate/{output_filename}"
    df.to_parquet(output_path)


if __name__ == "__main__":
    main()
