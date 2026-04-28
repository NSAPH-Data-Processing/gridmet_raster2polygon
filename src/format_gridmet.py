import duckdb 
import hydra
import os
import logging
from pathlib import Path

try:
    from src.gridmet_paths import data_root as resolve_data_root, final_output_path, intermediate_path
except ModuleNotFoundError:
    from gridmet_paths import data_root as resolve_data_root, final_output_path, intermediate_path

# configure logger to print at info level
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    # FLAG TO DISCUSS WITH GROUP
    #gridmet_vars = list(cfg.gridmet.variable_key.keys())
    gridmet_vars = cfg.snakemake.gridmet_vars
    data_root = resolve_data_root(cfg.datapaths, cfg.polygon_name)
    output_path = final_output_path(cfg.datapaths, cfg.polygon_name, "daily", cfg.year)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    LOGGER.info(f"Using data root: {data_root}")
    LOGGER.info(f"Joining GridMET variables")
    conn = duckdb.connect(f"datapond_{cfg.year}.db")

    # Create the first table
    LOGGER.info(f"Loading {gridmet_vars[0]}")
    conn.execute(f"""
        CREATE TABLE gridmet AS (
            SELECT 
                 {cfg.polygon_name}, 
                 day AS date, 
                 {gridmet_vars[0]}
            FROM
                '{intermediate_path(cfg.datapaths, cfg.polygon_name, gridmet_vars[0], cfg.year)}'
            WHERE
                {gridmet_vars[0]} IS NOT NULL
            )
    """)
 
    # Join all the gridmet variables
    for var in gridmet_vars[1:]:
        LOGGER.info(f"Loading {var}")
        conn.execute(f"""
            CREATE OR REPLACE TABLE gridmet_var AS (
                SELECT 
                     {cfg.polygon_name}, 
                     day AS date, 
                     {var} 
                FROM 
                    '{intermediate_path(cfg.datapaths, cfg.polygon_name, var, cfg.year)}'
                WHERE
                    {var} IS NOT NULL
                )
        """)

        LOGGER.info(f"Joining {var}")
        conn.execute(f"""
            CREATE OR REPLACE TABLE gridmet AS 
                (SELECT 
                    * 
                FROM 
                    gridmet 
                FULL JOIN 
                    gridmet_var 
                USING ({cfg.polygon_name}, date))
        """)

    # Output the fully joined table
    LOGGER.info(f"Outputting joined table")
    conn.execute(f"""
        COPY 
            (
                 SELECT * 
                 FROM gridmet
                 ORDER BY date, {cfg.polygon_name}
            ) 
        TO '{output_path}'
    """)

    # Clean up
    conn.close()
    os.remove(f"datapond_{cfg.year}.db")

if __name__ == "__main__":
    main()
