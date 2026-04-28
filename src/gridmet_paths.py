"""Shared path and filename helpers for GridMET pipeline outputs."""

from pathlib import Path
from typing import Any


def cfg_get(config: Any, key: str, default: Any = None) -> Any:
    """Read a key from a dict, DictConfig, or object-like config."""
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(key, default)
    try:
        return getattr(config, key)
    except (AttributeError, KeyError, TypeError):
        return default


def infer_product_name(datapaths_cfg: Any) -> str:
    """
    Return the product token used in LEGO GridMET parquet filenames.

    ``product_name`` is an optional override. Otherwise ``base_path`` is the
    product key, e.g. ``core`` or ``population_weighted``. Older configs with
    ``data/core`` still infer ``core``.
    """
    product_name = cfg_get(datapaths_cfg, "product_name")
    if product_name:
        return str(product_name)

    base_path = cfg_get(datapaths_cfg, "base_path")
    if base_path:
        return Path(str(base_path).rstrip("/")).name

    name = cfg_get(datapaths_cfg, "name")
    if name:
        name = str(name)
        return name.removeprefix("cannon_")

    raise ValueError("Cannot infer GridMET product name without base_path or product_name.")


def local_base_path(datapaths_cfg: Any, data_dir: str = "data") -> str:
    """
    Return the local workspace base path for a datapaths config.

    The canonical config value is a product key such as ``core``; local files
    live below ``data/{base_path}``. Absolute paths and older ``data/...``
    values are preserved for compatibility.
    """
    base_path = cfg_get(datapaths_cfg, "base_path")
    if base_path:
        path = Path(str(base_path))
        if path.is_absolute() or (path.parts and path.parts[0] == data_dir):
            return str(path)
        return str(Path(data_dir) / path)

    name = cfg_get(datapaths_cfg, "name")
    if name:
        return str(Path(data_dir) / str(name))
    return data_dir


def data_root(datapaths_cfg: Any, geo: str) -> str:
    """Return local data root for a geography, e.g. ``data/core/county``."""
    dirs_cfg = cfg_get(datapaths_cfg, "dirs")
    if cfg_get(dirs_cfg, geo) is not None:
        return str(Path(local_base_path(datapaths_cfg)) / geo)
    return local_base_path(datapaths_cfg)


def geo_dirs(datapaths_cfg: Any, geo: str) -> Any:
    """Return the geography-specific dirs block, with legacy fallback."""
    dirs_cfg = cfg_get(datapaths_cfg, "dirs")
    return cfg_get(dirs_cfg, geo, dirs_cfg)


def input_dir(datapaths_cfg: Any, geo: str, kind: str) -> str:
    """Return an input directory such as raw or shapefiles."""
    configured = cfg_get(cfg_get(geo_dirs(datapaths_cfg, geo), "input"), kind)
    if configured:
        return str(configured)
    return str(Path(data_root(datapaths_cfg, geo)) / "input" / kind)


def intermediate_dir(datapaths_cfg: Any, geo: str) -> str:
    """Return the per-variable intermediate parquet directory."""
    configured = cfg_get(geo_dirs(datapaths_cfg, geo), "intermediate")
    if configured:
        return str(configured)
    return str(Path(data_root(datapaths_cfg, geo)) / "intermediate")


def output_dir(datapaths_cfg: Any, geo: str, frequency: str) -> str:
    """Return an output directory for ``daily`` or ``yearly`` outputs."""
    configured = cfg_get(cfg_get(geo_dirs(datapaths_cfg, geo), "output"), frequency)
    if configured:
        return str(configured)
    return str(Path(data_root(datapaths_cfg, geo)) / "output" / frequency)


def raw_gridmet_path(datapaths_cfg: Any, geo: str, var: str, year: str | int) -> str:
    """Return the raw GridMET NetCDF path for a variable/year."""
    return str(Path(input_dir(datapaths_cfg, geo, "raw")) / f"{var}_{year}.nc")


def shapefile_root(datapaths_cfg: Any, geo: str) -> str:
    """Return the root directory containing yearly shapefile folders."""
    return input_dir(datapaths_cfg, geo, "shapefiles")


def intermediate_path(datapaths_cfg: Any, geo: str, var: str, year: str | int) -> str:
    """Return the per-variable intermediate parquet path."""
    return str(Path(intermediate_dir(datapaths_cfg, geo)) / f"{var}_{year}_{geo}.parquet")


def final_gridmet_filename(
    datapaths_cfg: Any,
    geo: str,
    frequency: str,
    year: str | int,
    product_name: str | None = None,
) -> str:
    """Return the LEGO final parquet filename."""
    product = product_name or infer_product_name(datapaths_cfg)
    return f"meteorology__gridmet__{product}__{geo}_{frequency}__{year}.parquet"


def final_output_path(
    datapaths_cfg: Any,
    geo: str,
    frequency: str,
    year: str | int,
    product_name: str | None = None,
) -> str:
    """Return a final daily/yearly GridMET parquet output path."""
    return str(
        Path(output_dir(datapaths_cfg, geo, frequency))
        / final_gridmet_filename(datapaths_cfg, geo, frequency, year, product_name)
    )


def population_output_path(datapaths_cfg: Any, year: str | int) -> str:
    """Return the yearly population GeoTIFF path for a datapaths config."""
    return str(
        Path(local_base_path(datapaths_cfg))
        / "population"
        / "output"
        / f"world_population__sedac__world_yearly__{year}.tif"
    )


def population_raw_dir(datapaths_cfg: Any) -> str:
    """Return the local raw population cache directory."""
    return str(Path(local_base_path(datapaths_cfg)) / "population" / "input" / "raw")


def population_output_dir(datapaths_cfg: Any) -> str:
    """Return the local population output directory."""
    return str(Path(local_base_path(datapaths_cfg)) / "population" / "output")


def load_datapaths_config(name: str, config_root: str | Path | None = None) -> Any:
    """Load a datapaths YAML config by name."""
    from omegaconf import OmegaConf

    root = Path(config_root) if config_root else Path(__file__).resolve().parents[1] / "conf" / "datapaths"
    return OmegaConf.load(root / f"{name}.yaml")
