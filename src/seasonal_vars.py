"""
Create seasonal aggregates from daily gridMET data for a single year.

This script reads daily parquet files and creates seasonal averages based on
configurable season definitions from conf/seasons.yaml.

Default seasons:
- Spring: March 1 - May 31
- Summer: June 1 - August 31
- Fall: September 1 - November 30
- Winter: December 1 (previous year) - February 28/29 (current year)

adapted from: https://github.com/NSAPH/National-Causal-Analysis/blob/master/Confounders/earth_engine/code/6_calculate_seasonal_averages.R

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


def build_season_filter(season_name: str, season_config: dict, year: int) -> str:
    """
    Build a SQL WHERE clause filter for a season.
    
    Args:
        season_name: Name of the season (e.g., 'summer', 'winter')
        season_config: Dictionary with start_month, start_day, end_month, end_day, year_offset
        year: The year being processed
    
    Returns:
        SQL WHERE clause string
    """
    year_offset = season_config.get('year_offset', 0)
    start_month = season_config['start_month']
    end_month = season_config['end_month']
    
    if year_offset == 0:
        # Simple case: season within the same year
        if start_month <= end_month:
            # Normal season (e.g., summer: June-August)
            return f"""data_year = {year} 
              AND month >= {start_month} AND month <= {end_month}"""
        else:
            # Season wraps around year boundary within same year (unusual but supported)
            return f"""data_year = {year} 
              AND (month >= {start_month} OR month <= {end_month})"""
    else:
        # Season spans year boundary (e.g., winter: Dec previous year + Jan-Feb current year)
        if year_offset == -1:
            # Previous year contributes to this year's season
            return f"""(data_year = {year - 1} AND month >= {start_month})
            OR (data_year = {year} AND month <= {end_month})"""
        else:
            LOGGER.warning(f"Unusual year_offset {year_offset} for season {season_name}")
            return f"data_year = {year} AND month >= {start_month} AND month <= {end_month}"


@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    """
    Create seasonal aggregates for gridMET data for a single year.
    
    This function processes daily gridMET data to create seasonal averages
    based on the seasons defined in cfg.seasons configuration.
    
    Args:
        cfg: Hydra configuration object containing:
            - year: Year to process (single year)
            - polygon_name: Geographic identifier column name (e.g., 'zcta', 'county')
            - datapaths.name: Geographic area name for file paths
            - snakemake.gridmet_vars: List of gridMET variables to aggregate
            - seasons: Dictionary of season definitions with start/end months/days
    """
    geo_name = cfg.datapaths.name
    polygon_name = cfg.polygon_name
    gridmet_vars = cfg.snakemake.gridmet_vars
    year = cfg.year
    seasons = cfg.seasons
    
    LOGGER.info(f"Creating seasonal aggregates for {geo_name}, year {year}")
    LOGGER.info(f"Variables: {', '.join(gridmet_vars)}")
    LOGGER.info(f"Seasons configured: {', '.join(seasons.keys())}")
    
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
    
    # Process each configured season
    seasonal_tables = {}
    
    for season_name, season_config in seasons.items():
        LOGGER.info(f"Calculating {season_name} {year} averages...")
        
        # Build aggregation expressions
        agg_exprs = [f"AVG({var}) AS {season_name}_{var}" for var in gridmet_vars]
        
        # Build WHERE clause for this season
        season_filter = build_season_filter(season_name, season_config, year)
        
        # Create table for this season
        table_name = f"{season_name}_aggregates"
        conn.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT
                {polygon_name},
                {year} AS year,
                {', '.join(agg_exprs)}
            FROM all_daily_data
            WHERE {season_filter}
            GROUP BY {polygon_name}
        """)
        
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        LOGGER.info(f"{season_name.capitalize()} aggregates created: {count:,} records")
        seasonal_tables[season_name] = table_name
    
    # Merge all seasonal data
    LOGGER.info(f"Merging all {len(seasonal_tables)} seasonal aggregates...")
    
    conn.execute(f"""
        CREATE OR REPLACE TABLE seasonal_combined AS
        SELECT
            COALESCE(sp.{polygon_name}, su.{polygon_name}, f.{polygon_name}, w.{polygon_name}) AS {polygon_name},
            {year} AS year,
            {', '.join([f'sp.spring_{var}' for var in gridmet_vars])},
            {', '.join([f'su.summer_{var}' for var in gridmet_vars])},
            {', '.join([f'f.fall_{var}' for var in gridmet_vars])},
            {', '.join([f'w.winter_{var}' for var in gridmet_vars])}
        FROM spring_aggregates sp
        FULL OUTER JOIN summer_aggregates su
            ON sp.{polygon_name} = su.{polygon_name}
        FULL OUTER JOIN fall_aggregates f
            ON COALESCE(sp.{polygon_name}, su.{polygon_name}) = f.{polygon_name}
        FULL OUTER JOIN winter_aggregates w
            ON COALESCE(sp.{polygon_name}, su.{polygon_name}, f.{polygon_name}) = w.{polygon_name}
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
