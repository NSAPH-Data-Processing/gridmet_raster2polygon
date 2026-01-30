"""
Create seasonal aggregates from daily gridMET data for a single year.

This script reads daily parquet files and creates seasonal averages based on
configurable season definitions from conf/seasons.yaml.

Default seasons:
- Summer: June 1 - August 31
- Winter: January 1 - February 28/29 and December 1 - December 31 (of the same year)

adapted from: https://github.com/NSAPH/National-Causal-Analysis/blob/master/Confounders/earth_engine/code/6_calculate_seasonal_averages.R

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
    Build a SQL WHERE clause filter for a season based on explicit month list.
    
    Args:
        season_name: Name of the season (e.g., 'summer', 'winter')
        season_config: Dictionary with 'months' (list of month numbers) and 'year_offset'
        year: The year being processed
    
    Returns:
        SQL WHERE clause string
    """
    months = season_config.get('months', [])
    year_offset = season_config.get('year_offset', 0)
    
    if not months:
        LOGGER.error(f"No months specified for season {season_name}")
        return "1=0"  # Returns no rows
    
    target_year = year + year_offset
    month_conditions = " OR ".join([f"month = {m}" for m in months])
    
    LOGGER.info(f"{season_name}: months {months} from year {target_year}")
    
    return f"""data_year = {target_year} AND ({month_conditions})"""


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
    
    # Load current year data only
    data_dir = Path(f"data/{geo_name}/output/daily")
    current_year_file = data_dir / f"meteorology__gridmet__{polygon_name}_daily__{year}.parquet"
    
    if not current_year_file.exists():
        LOGGER.error(f"Daily file not found for year {year}: {current_year_file}")
        return
    
    LOGGER.info(f"Loading daily data from: {current_year_file}")
    
    conn.execute(f"""
        CREATE OR REPLACE VIEW all_daily_data AS
        SELECT 
            {polygon_name},
            date,
            EXTRACT(YEAR FROM date) AS data_year,
            EXTRACT(MONTH FROM date) AS month,
            EXTRACT(DAY FROM date) AS day,
            {', '.join(gridmet_vars)}
        FROM read_parquet('{current_year_file}')
    """)
    
    # Check total records
    total_records = conn.execute("SELECT COUNT(*) FROM all_daily_data").fetchone()[0]
    LOGGER.info(f"Total daily records loaded: {total_records:,}")
    
    # Process each configured season
    seasonal_tables = {}
    
    for season_name, season_config in seasons.items():
        LOGGER.info(f"Calculating {season_name} {year} averages...")
        
        # Build aggregation expressions
        agg_exprs = [f"AVG({var}) AS {var}_{season_name}" for var in gridmet_vars]
        
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
    
    # Build dynamic JOIN query based on available seasons
    season_names = list(seasonal_tables.keys())
    
    if len(season_names) == 0:
        LOGGER.error("No seasonal tables to merge")
        return
    
    # Build SELECT columns for all seasons
    select_columns = []
    for season_name in season_names:
        season_abbrev = season_name[:2] if len(season_name) >= 2 else season_name[0]
        select_columns.extend([f'{season_abbrev}.{var}_{season_name}' for var in gridmet_vars])
    
    # Build COALESCE for polygon_name across all tables
    season_abbrevs = [s[:2] if len(s) >= 2 else s[0] for s in season_names]
    coalesce_expr = f"COALESCE({', '.join([f'{abbrev}.{polygon_name}' for abbrev in season_abbrevs])})"
    
    # Build JOIN clause dynamically
    first_season = season_names[0]
    first_abbrev = season_abbrevs[0]
    from_clause = f"FROM {first_season}_aggregates {first_abbrev}"
    
    for i in range(1, len(season_names)):
        season_name = season_names[i]
        season_abbrev = season_abbrevs[i]
        prev_abbrevs = season_abbrevs[:i]
        prev_coalesce = f"COALESCE({', '.join([f'{abbrev}.{polygon_name}' for abbrev in prev_abbrevs])})"
        from_clause += f"\n        FULL OUTER JOIN {season_name}_aggregates {season_abbrev}\n"
        from_clause += f"            ON {prev_coalesce} = {season_abbrev}.{polygon_name}"
    
    conn.execute(f"""
        CREATE OR REPLACE TABLE seasonal_combined AS
        SELECT
            {coalesce_expr} AS {polygon_name},
            {year} AS year,
            {', '.join(select_columns)}
        {from_clause}
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
