import duckdb

def format_gridmet():
    # Load the data
    conn = duckdb.connect(database=':memory:', read_only=False)
    conn.execute("CREATE TABLE gridmet (lon FLOAT, lat FLOAT, day DATE, value FLOAT)")
    conn.execute("COPY gridmet FROM 'data/input/gridmet.csv' (delimiter ',')")

    # Compute the downscaling factor
    downscaling_factor = 1

    # Compute the mapping from vector geometries to raster cells
    conn.execute("CREATE TABLE poly2cells AS SELECT * FROM polygon_to_raster_cells('polygon.geometry', 'gridmet', 'lon', 'lat', 'value', 'day', ?, ?, ?, ?, ?)", (downscaling_factor, downscaling_factor, True, None, False))

    # Compute the zonal stats for each day
    conn.execute("CREATE TABLE zonal_stats AS SELECT * FROM zonal_stats('poly2cells', 'gridmet', 'lon', 'lat', 'value', 'day', ?, ?)", (downscaling_factor, downscaling_factor))

    # Output the results
    conn.execute("COPY zonal_stats TO 'data/output/zonal_stats.csv' (delimiter ',')")

    # Clean up
    conn.close()