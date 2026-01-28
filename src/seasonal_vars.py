"""
Create seasonal aggregates from daily gridMET data for a single year.

This script reads daily parquet files and creates seasonal averages for one year:
- Summer: June 1 - August 31 of the specified year
- Winter: December 1 (previous year) - February 28/29 (current year)

The logic mirrors the R script that processes temperature data, calculating
mean values for all gridMET variables by geographic unit and season.

This script is designed to be orchestrated by Snakemake to process multiple years.
"""

import duckdb
import hydra
import logging
from pathlib import Path

# Configure logger
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """
    Create seasonal aggregates for gridMET data for a single year.
    
    This function processes daily gridMET data to create summer and winter
    seasonal averages for all meteorological variables for cfg.year.
    
    Args:
        cfg: Hydra configuration object containing:
            - year: Year to process (single year)
            - polygon_name: Geographic identifier column name (e.g., 'zcta', 'county')
            - datapaths.name: Geographic area name for file paths
            - snakemake.gridmet_vars: List of gridMET variables to aggregate
    """
    geo_name = cfg.datapaths.name
    polygon_name = cfg.polygon_name
    gridmet_vars = cfg.snakemake.gridmet_vars
    year = cfg.year
    
    LOGGER.info(f"Creating seasonal aggregates for {geo_name}, year {year}")
    LOGGER.info(f"Variables: {', '.join(gridmet_vars)}")
    
    # Initialize DuckDB connection
    conn = duckdb.connect()
    
    # Check which files we need: current year and previous year (for winter)
    data_dir = Path(f"data/{geo_name}/output/daily")
    current_year_file = data_dir / f"meteorology__gridmet__{polygon_name}_daily__{year}.parquet"
    prev_year_file = data_dir / f"meteorology__gridmet__{polygon_name}_daily__{year - 1}.parquet"
    
    if not current_year_file.exists():
        LOGGER.error(f"Daily file not found for year {year}: {current_year_file}")
        return
    
    # Winter calculation needs previous year's December
    if not prev_year_file.exists():
        LOGGER.warning(f"Previous year file not found: {prev_year_file}")
        LOGGER.warning(f"Winter average for {year} will only include Jan-Feb data")
        files_to_load = [str(current_year_file)]
    else:
        files_to_load = [str(prev_year_file), str(current_year_file)]
    
    LOGGER.info(f"Loading daily data from: {files_to_load}")
    
    # Load data from the necessary files
    file_list_str = ", ".join([f"'{f}'" for f in files_to_load])
    
    conn.execute(f"""
        CREATE OR REPLACE VIEW all_daily_data AS
        SELECT 
            {polygon_name},
            date,
            EXTRACT(YEAR FROM date) AS data_year,
            EXTRACT(MONTH FROM date) AS month,
            EXTRACT(DAY FROM date) AS day,
            {', '.join(gridmet_vars)}
        FROM read_parquet([{file_list_str}])
    """)
    
    # Check total records
    total_records = conn.execute("SELECT COUNT(*) FROM all_daily_data").fetchone()[0]
    LOGGER.info(f"Total daily records loaded: {total_records:,}")
    
    # Process summer season (June 1 - August 31) for the current year
    LOGGER.info(f"Calculating summer {year} averages (June 1 - August 31)...")
    
    summer_agg_exprs = [f"AVG({var}) AS summer_{var}" for var in gridmet_vars]
    
    conn.execute(f"""
        CREATE OR REPLACE TABLE summer_aggregates AS
        SELECT
            {polygon_name},
            {year} AS year,
            {', '.join(summer_agg_exprs)}
        FROM all_daily_data
        WHERE data_year = {year}
          AND month >= 6 AND month <= 8  -- June, July, August
        GROUP BY {polygon_name}
    """)
    
    summer_count = conn.execute("SELECT COUNT(*) FROM summer_aggregates").fetchone()[0]
    LOGGER.info(f"Summer aggregates created: {summer_count:,} records")
    
    # Process winter season (December previous year - February current year)
    LOGGER.info(f"Calculating winter {year} averages (Dec {year-1} - Feb {year})...")
    
    winter_agg_exprs = [f"AVG({var}) AS winter_{var}" for var in gridmet_vars]
    
    # Winter for year Y includes: Dec (Y-1) + Jan-Feb (Y)
    conn.execute(f"""
        CREATE OR REPLACE TABLE winter_aggregates AS
        SELECT
            {polygon_name},
            {year} AS year,
            {', '.join(winter_agg_exprs)}
        FROM all_daily_data
        WHERE 
            (data_year = {year - 1} AND month = 12)  -- December of previous year
            OR (data_year = {year} AND month <= 2)   -- January and February of current year
        GROUP BY {polygon_name}
    """)
    
    winter_count = conn.execute("SELECT COUNT(*) FROM winter_aggregates").fetchone()[0]
    LOGGER.info(f"Winter aggregates created: {winter_count:,} records")
    
    # Merge summer and winter data
    LOGGER.info("Merging summer and winter aggregates...")
    
    conn.execute(f"""
        CREATE OR REPLACE TABLE seasonal_combined AS
        SELECT
            COALESCE(s.{polygon_name}, w.{polygon_name}) AS {polygon_name},
            {year} AS year,
            {', '.join([f's.summer_{var}' for var in gridmet_vars])},
            {', '.join([f'w.winter_{var}' for var in gridmet_vars])}
        FROM summer_aggregates s
        FULL OUTER JOIN winter_aggregates w
            ON s.{polygon_name} = w.{polygon_name}
        ORDER BY {polygon_name}
    """)
    
    combined_count = conn.execute("SELECT COUNT(*) FROM seasonal_combined").fetchone()[0]
    LOGGER.info(f"Combined seasonal data: {combined_count:,} records")
    
    # Show sample of the output
    LOGGER.info("Sample of seasonal aggregates:")
    sample = conn.execute("SELECT * FROM seasonal_combined LIMIT 5").fetchdf()
    LOGGER.info(f"\n{sample.to_string()}")
    
    # Create output directory if it doesn't exist
    output_dir = Path(f"data/{geo_name}/output/seasonal")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write output to parquet file
    output_path = output_dir / f"meteorology__gridmet__{polygon_name}_seasonal__{year}.parquet"
    LOGGER.info(f"Writing output to: {output_path}")
    
    conn.execute(f"""
        COPY seasonal_combined
        TO '{output_path}'
        (FORMAT PARQUET)
    """)
    
    LOGGER.info(f"Seasonal aggregates successfully written to {output_path}")
    
    # Clean up
    conn.close()
    LOGGER.info("Processing complete!")


if __name__ == "__main__":
    main()
