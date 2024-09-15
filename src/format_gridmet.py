import duckdb
import hydra
import os

@hydra.main(config_path="../conf", config_name="config", version_base=None)
def main(cfg):
    gridmet_vars = list(cfg.gridmet.variable_key.keys())
    # Load the data
    conn = duckdb.connect("datapond.db")

    conn.execute(f"""
        CREATE TABLE gridmet AS 
            (SELECT 
                 county, 
                 day, 
                 {gridmet_vars[0]} 
            FROM 
                'data/intermediate/{gridmet_vars[0]}_{cfg.year}_{cfg.polygon_name}.parquet')
    """)
 
    # Join all the gridmet variables
    for var in gridmet_vars[1:]:
        conn.execute(f"""
            CREATE OR REPLACE TABLE gridmet_var AS
                (SELECT 
                     county, 
                     day, 
                     {var} 
                FROM 
                    'data/intermediate/{var}_{cfg.year}_{cfg.polygon_name}.parquet')
        """)

        conn.execute("""
            CREATE OR REPLACE TABLE gridmet AS 
                (SELECT 
                    * 
                FROM 
                    gridmet 
                FULL JOIN 
                    gridmet_var 
                USING (county, day))
        """)

    # Output the fully joined table
    conn.execute(f"""
        COPY 
            (SELECT * FROM gridmet) 
        TO 'data/output/gridmet_{cfg.year}.parquet'
    """)

    # Clean up
    conn.close()
    os.remove("datapond.db")

if __name__ == "__main__":
    if os.path.exists("datapond.db"):
        os.remove("datapond.db")
        print("File datapond.db removed")
    main()