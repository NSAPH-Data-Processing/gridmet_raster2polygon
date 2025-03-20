import duckdb 
import hydra
import os
import logging

# configure logger to print at info level
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    gridmet_vars = cfg.snakemake.gridmet_vars
    geo_name = cfg.datapaths.name
    conn = duckdb.connect()

    # Obtain yearly summary statistics
    LOGGER.info(f"Obtaining yearly summary statistics for year {cfg.year}")
    LOGGER.info(f"Adding 'year' column to gridmet table for year {cfg.year}")
    conn.execute(f"""
        CREATE OR REPLACE TABLE gridmet AS (
            SELECT 
                {cfg.polygon_name},
                date,
                EXTRACT(YEAR FROM date) AS year,
                {', '.join(gridmet_vars)}
            FROM 
                'data/{geo_name}/output/daily/meteorology__gridmet__{cfg.polygon_name}_daily__{cfg.year}.parquet'
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
        TO 'data/{geo_name}/output/yearly/meteorology__gridmet__{cfg.polygon_name}_yearly__{cfg.year}.parquet'
    """)
    
    LOGGER.info(f"Outputted yearly stats table to 'data/{geo_name}/output/yearly/meteorology_{cfg.polygon_name}_yearly_{cfg.year}.parquet'")
    conn.close()

if __name__ == "__main__":
    # if os.path.exists("datapond.db"):
    #     os.remove("datapond.db")
    #     print("File datapond.db removed")
    main()