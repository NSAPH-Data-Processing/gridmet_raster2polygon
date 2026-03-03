import duckdb 
import hydra
import os
import logging

# configure logger to print at info level
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    # FLAG TO DISCUSS WITH GROUP
    #gridmet_vars = list(cfg.gridmet.variable_key.keys())
    gridmet_vars = cfg.snakemake.gridmet_vars
    geo_name = cfg.datapaths.name
    base_path = getattr(cfg.datapaths, 'base_path', None)
    if geo_name is not None:
        data_root = base_path or f"data/{geo_name}"
    else:
        data_root = f"{base_path}/{cfg.polygon_name}"

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
                '{data_root}/intermediate/{gridmet_vars[0]}_{cfg.year}_{cfg.polygon_name}.parquet'
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
                    '{data_root}/intermediate/{var}_{cfg.year}_{cfg.polygon_name}.parquet'
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
        TO '{data_root}/output/daily/meteorology__gridmet__{cfg.polygon_name}_daily__{cfg.year}.parquet'
    """)

    # Clean up
    conn.close()
    os.remove(f"datapond_{cfg.year}.db")

if __name__ == "__main__":
    # if os.path.exists("datapond.db"):
    #     os.remove("datapond.db")
    #     print("File datapond.db removed")
    main()