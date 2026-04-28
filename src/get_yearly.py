import duckdb 
import hydra
import os
import logging
from pathlib import Path

try:
    from src.gridmet_paths import data_root as resolve_data_root, final_output_path
except ModuleNotFoundError:
    from gridmet_paths import data_root as resolve_data_root, final_output_path

# configure logger to print at info level
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    gridmet_vars = cfg.snakemake.gridmet_vars
    data_root = resolve_data_root(cfg.datapaths, cfg.polygon_name)
    daily_path = final_output_path(cfg.datapaths, cfg.polygon_name, "daily", cfg.year)
    yearly_path = final_output_path(cfg.datapaths, cfg.polygon_name, "yearly", cfg.year)
    Path(yearly_path).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()

    # Obtain yearly summary statistics
    LOGGER.info(f"Obtaining yearly summary statistics for year {cfg.year}")
    LOGGER.info(f"Using data root: {data_root}")
    LOGGER.info(f"Adding 'year' column to gridmet table for year {cfg.year}")
    conn.execute(f"""
        CREATE OR REPLACE TABLE gridmet AS (
            SELECT 
                {cfg.polygon_name},
                date,
                EXTRACT(YEAR FROM date) AS year,
                {', '.join(gridmet_vars)}
            FROM 
                '{daily_path}'
        )
    """)

    conn.execute(f"""
        CREATE TABLE gridmet_yearly_stats AS (
            SELECT
                {cfg.polygon_name},
                year,
                {', '.join([
                    f"AVG({var}) AS {var}"
                    for var in gridmet_vars
                ])}
            FROM
                gridmet
            GROUP BY
                {cfg.polygon_name}, year
        )
    """)
    #f"AVG({var}) AS avg_{var}, MIN({var}) AS min_{var}, MAX({var}) AS max_{var}, STDDEV({var}) AS sd_{var}"
    LOGGER.info(f"nrows of yearly gridmet {cfg.year}: {conn.execute('SELECT COUNT(*) FROM gridmet_yearly_stats').fetchone()}")
    LOGGER.info(f"head of yearly gridmet {cfg.year}: {conn.execute('SELECT * FROM gridmet_yearly_stats LIMIT 10').fetchdf()}")

    # Output the yearly stats table
    LOGGER.info(f"Outputting the yearly stats table for year {cfg.year}")
    conn.execute(f"""
        COPY 
            (
                 SELECT * 
                 FROM gridmet_yearly_stats
                 ORDER BY year, {cfg.polygon_name}
            ) 
        TO '{yearly_path}'
    """)
    
    LOGGER.info(f"Outputted yearly stats table to '{yearly_path}'")
    conn.close()

if __name__ == "__main__":
    # if os.path.exists("datapond.db"):
    #     os.remove("datapond.db")
    #     print("File datapond.db removed")
    main()
