import duckdb 
import hydra
import os
import logging

# configure logger to print at info level
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    gridmet_vars = list(cfg.gridmet.variable_key.keys())
    
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
                'data/intermediate/{gridmet_vars[0]}_{cfg.year}_{cfg.polygon_name}.parquet'
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
                    'data/intermediate/{var}_{cfg.year}_{cfg.polygon_name}.parquet'
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
        TO 'data/output/gridmet_{cfg.year}.parquet'
    """)

    # Clean up
    conn.close()
    os.remove(f"datapond_{cfg.year}.db")

if __name__ == "__main__":
    # if os.path.exists("datapond.db"):
    #     os.remove("datapond.db")
    #     print("File datapond.db removed")
    main()