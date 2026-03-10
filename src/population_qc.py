"""
population_qc.py
----------------
Standalone QC script comparing population-weighted vs unweighted gridMET
yearly aggregations produced by get_yearly.py.

Usage
-----
    python src/population_qc.py --config-name population_qc
    python src/population_qc.py --config-name population_qc polygon_name=zcta
    python src/population_qc.py --config-name population_qc var=rmin years=[2010,2015,2020]

Inputs
------
- weighted_dir   : directory of yearly parquets from a population-weighted
                   get_yearly.py run.
                   Expected filename: meteorology__gridmet__{polygon}_yearly__{year}.parquet
- unweighted_dir : directory of yearly parquets from the core (unweighted)
                   get_yearly.py run (same filename pattern).
- polygon_name   : geographic unit identifier column (e.g. county, zcta).
- shapefile      : path to a .shp file used for spatial maps.
- output_dir     : directory where PNG plots will be saved.
- var            : gridMET variable shortname (e.g. rmin). If omitted, all
                   variables present in both datasets are plotted.
- years          : optional list of years to include; defaults to all matched years.

Output
------
One 4-panel PNG per variable:
  1. Annual spatial-mean time series (weighted vs unweighted)
  2. Scatter   – weighted vs unweighted per polygon-year
  3. Histogram – distribution of per-polygon-year differences
  4. Spatial   – choropleth of the difference for the most recent year
"""

import glob
import logging
import os

import geopandas as gpd
import hydra
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from omegaconf import OmegaConf

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

VARIABLE_KEY = {
    "sph":  "near-surface specific humidity",
    "vpd":  "mean vapor pressure deficit",
    "tmmn": "minimum near-surface air temperature",
    "tmmx": "maximum near-surface air temperature",
    "pr":   "precipitation",
    "rmin": "minimum near-surface relative humidity",
    "rmax": "maximum near-surface relative humidity",
    "srad": "surface downwelling solar radiation",
    "vs":   "wind speed at 10m",
    "th":   "wind direction at 10m",
}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_yearly_dir(directory: str, polygon_name: str, years: list = None) -> pd.DataFrame:
    """
    Load all yearly parquets from *directory* matching the pattern
    ``meteorology__gridmet__{polygon_name}_yearly__*.parquet``.

    Parameters
    ----------
    directory : str
    polygon_name : str  e.g. "county" or "zcta"
    years : list of int, optional – if given, only load those years

    Returns
    -------
    pd.DataFrame  (concatenated across all matched years)
    """
    pattern = os.path.join(directory, f"meteorology__gridmet__{polygon_name}_yearly__*.parquet")
    paths = sorted(glob.glob(pattern))

    if not paths:
        raise FileNotFoundError(
            f"No parquets matching '{pattern}' found in '{directory}'."
        )

    if years:
        year_strs = {str(y) for y in years}
        paths = [p for p in paths if os.path.basename(p).split("__")[-1].replace(".parquet", "") in year_strs]
        if not paths:
            raise FileNotFoundError(f"No matching parquets for years {years} in '{directory}'.")

    chunks = [pd.read_parquet(p) for p in paths]
    df = pd.concat(chunks, ignore_index=True)
    LOGGER.info(f"Loaded {len(paths)} file(s) from '{directory}' → {len(df):,} rows")
    return df


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_qc(
    df_w: pd.DataFrame,
    df_u: pd.DataFrame,
    var: str,
    polygon_name: str,
    polygon: gpd.GeoDataFrame,
    output_dir: str,
):
    """
    Generate a 4-panel QC figure comparing weighted vs unweighted annual means.

    Parameters
    ----------
    df_w : pd.DataFrame
        Weighted yearly data with columns [polygon_name, year, <var>, ...]
    df_u : pd.DataFrame
        Unweighted yearly data (same schema).
    var : str
        gridMET variable shortname to plot.
    polygon_name : str
        Column name identifying each geographic unit.
    polygon : gpd.GeoDataFrame
        Shapefile geometries (used for the spatial panel).
    output_dir : str
        Destination directory for the saved PNG.
    """
    desc = VARIABLE_KEY.get(var, var)

    # -- Align: keep only (polygon, year) rows present in both --
    key_cols = [polygon_name, "year"]
    merged = pd.merge(
        df_w[[polygon_name, "year", var]].rename(columns={var: "weighted"}),
        df_u[[polygon_name, "year", var]].rename(columns={var: "unweighted"}),
        on=key_cols,
        how="inner",
    )
    if merged.empty:
        LOGGER.warning(f"No overlapping (polygon, year) rows for var={var}; skipping.")
        return

    years_available = sorted(merged["year"].unique())
    LOGGER.info(f"Plotting QC for var={var}, years={years_available[0]}–{years_available[-1]}, "
                f"n_polygon_years={len(merged):,}")

    fig = plt.figure(figsize=(16, 14))
    gs = gridspec.GridSpec(2, 2, hspace=0.35, wspace=0.3)

    # --- Panel 1: annual spatial-mean time series ---
    annual_w = merged.groupby("year")["weighted"].mean()
    annual_u = merged.groupby("year")["unweighted"].mean()

    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(annual_u.index, annual_u.values, marker="o", markersize=4,
             label="Unweighted", alpha=0.85, linewidth=1.2)
    ax1.plot(annual_w.index, annual_w.values, marker="o", markersize=4,
             label="Pop-weighted", alpha=0.85, linewidth=1.2)
    ax1.set_xlabel("Year")
    ax1.set_ylabel(f"{desc} ({var})")
    ax1.set_title(f"Annual Mean Across All {polygon_name}s")
    ax1.legend()
    ax1.tick_params(axis="x", rotation=45)

    # --- Panel 2: scatter – weighted vs unweighted per polygon-year ---
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.scatter(
        merged["unweighted"].values,
        merged["weighted"].values,
        s=2, alpha=0.3, edgecolors="none",
    )
    lims = [
        min(merged["unweighted"].min(), merged["weighted"].min()),
        max(merged["unweighted"].max(), merged["weighted"].max()),
    ]
    ax2.plot(lims, lims, "r--", linewidth=0.8, label="1:1 line")
    ax2.set_xlabel(f"Unweighted {var}")
    ax2.set_ylabel(f"Pop-weighted {var}")
    ax2.set_title(f"Weighted vs Unweighted (all {polygon_name}-years)")
    ax2.legend(loc="upper left")

    # --- Panel 3: histogram of differences ---
    diff = merged["weighted"].values - merged["unweighted"].values
    diff = diff[np.isfinite(diff)]
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.hist(diff, bins=60, edgecolor="black", linewidth=0.3, alpha=0.7)
    ax3.axvline(0, color="red", linestyle="--", linewidth=0.8)
    ax3.set_xlabel("Difference (weighted − unweighted)")
    ax3.set_ylabel("Count")
    years_str = (f"{years_available[0]}–{years_available[-1]}"
                 if len(years_available) > 1 else str(years_available[0]))
    ax3.set_title(f"Distribution of Differences ({years_str})")
    ax3.text(
        0.95, 0.95,
        f"median = {np.median(diff):.4f}\nstd = {np.std(diff):.4f}",
        transform=ax3.transAxes, ha="right", va="top",
        fontsize=9, bbox=dict(facecolor="white", alpha=0.8),
    )

    # --- Panel 4: spatial map for the most recent year ---
    latest_year = years_available[-1]
    subset = merged[merged["year"] == latest_year].copy()
    subset["diff"] = subset["weighted"] - subset["unweighted"]

    # Merge with shapefile geometry on polygon_name column
    gdf_diff = polygon.merge(
        subset[[polygon_name, "diff"]],
        on=polygon_name,
        how="left",
    )

    ax4 = fig.add_subplot(gs[1, 1])
    spatial_diff = gdf_diff["diff"].values
    finite_vals = spatial_diff[np.isfinite(spatial_diff)]
    vmax = max(abs(finite_vals.min()), abs(finite_vals.max())) if len(finite_vals) else 1
    if vmax == 0:
        vmax = 1

    gdf_diff.plot(
        column="diff", ax=ax4, legend=True, cmap="RdBu_r",
        vmin=-vmax, vmax=vmax,
        missing_kwds={"color": "lightgrey"},
        legend_kwds={"label": f"Δ {var} (weighted − unweighted)", "shrink": 0.6},
    )
    ax4.set_title(f"Spatial Difference – {latest_year}")
    ax4.set_xlim(-125, -65)
    ax4.set_ylim(25, 50)
    ax4.set_axis_off()

    fig.suptitle(
        f"Population Weighting QC: {desc} ({var}), {polygon_name}, {years_str}",
        fontsize=14, fontweight="bold", y=0.98,
    )

    os.makedirs(output_dir, exist_ok=True)
    png_path = os.path.join(output_dir, f"pop_qc_{var}_{polygon_name}_{years_str}.png")
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    LOGGER.info(f"Saved: {png_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@hydra.main(config_path="../conf", config_name="population_qc", version_base=None)
def main(cfg):
    years = list(cfg.years) if cfg.years is not None else None

    LOGGER.info("Loading weighted yearly data...")
    df_w = _load_yearly_dir(cfg.weighted_yearly_dir, cfg.polygon_name, years)

    LOGGER.info("Loading unweighted yearly data...")
    df_u = _load_yearly_dir(cfg.unweighted_yearly_dir, cfg.polygon_name, years)

    # Resolve shapefile path the same way as aggregate_gridmet.py
    shapefile_nm = cfg.shapefile_prefix + str(cfg.shapefile_year)
    shapefile_path = f"{cfg.shapefile_dir}/{shapefile_nm}/{shapefile_nm}.shp"
    LOGGER.info(f"Loading shapefile: {shapefile_path}")
    polygon = gpd.read_file(shapefile_path)

    # Ensure the polygon_name column is present (case-insensitive fallback)
    if cfg.polygon_name not in polygon.columns:
        matches = [c for c in polygon.columns if c.lower() == cfg.polygon_name.lower()]
        if matches:
            polygon = polygon.rename(columns={matches[0]: cfg.polygon_name})
            LOGGER.info(f"Renamed shapefile column '{matches[0]}' → '{cfg.polygon_name}'")
        else:
            LOGGER.warning(
                f"Column '{cfg.polygon_name}' not found in shapefile. "
                f"Available columns: {polygon.columns.tolist()}"
            )

    # Determine variables to plot
    if cfg.var:
        vars_to_plot = [cfg.var]
    else:
        data_vars = (set(df_w.columns) & set(df_u.columns)) - {"year", cfg.polygon_name}
        vars_to_plot = sorted(data_vars & set(VARIABLE_KEY.keys()))
        LOGGER.info(f"No var specified; plotting all variables: {vars_to_plot}")

    for var in vars_to_plot:
        if var not in df_w.columns:
            LOGGER.warning(f"Variable '{var}' not in weighted data; skipping.")
            continue
        if var not in df_u.columns:
            LOGGER.warning(f"Variable '{var}' not in unweighted data; skipping.")
            continue
        plot_qc(df_w, df_u, var, cfg.polygon_name, polygon, cfg.output_dir)

    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
