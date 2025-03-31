import simplekml
import geopy.distance
import math
import webbrowser  # Import webbrowser to automatically open the file after saving
import os
from geopy.distance import geodesic

def calculate_initial_compass_bearing(pointA, pointB):
    """
    Calculates the bearing between two points.
    The formula used to calculate the bearing is based on the haversine formula.
    """
    lat1 = math.radians(pointA[0])
    lat2 = math.radians(pointB[0])

    diffLong = math.radians(pointB[1] - pointA[1])

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(diffLong))
    initial_bearing = math.atan2(x, y)
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing

def rotate_point(lat, lon, angle, origin_lat, origin_lon):
    # Convert the angle to radians
    angle_rad = math.radians(angle)

    # Convert lat/lon to x, y (meters from the origin)
    origin = (origin_lat, origin_lon)
    point = (lat, lon)

    # Calculate the distance and bearing from the origin to the point
    distance = geopy.distance.distance(origin, point).m
    bearing = calculate_initial_compass_bearing(origin, point)
    
    # Apply rotation to the bearing
    new_bearing = bearing + angle  # Rotate the bearing by the specified angle
    
    # Calculate the new coordinates after rotation
    new_point = geopy.distance.distance(kilometers=distance / 1000).destination(origin, new_bearing)
    new_lat, new_lon = new_point.latitude, new_point.longitude

    return new_lat, new_lon


def fetch_all_survey_numbers(connections):
    all_keys = []
    for conn in connections:
        keys = list(conn.keys())
        all_keys.extend(keys)
    return all_keys

def generate_grids_kml(grid_configs, output_filename="grid.kml"):
    kml = simplekml.Kml()  # Create a new KML object
    original_start_lat = None
    original_start_lon = None
    combined_coordinates = {}
    
    for config in grid_configs:
        start_lat = config["start_lat"]
        start_lon = config["start_lon"]
        rows = config["rows"]
        cols = config["cols"]
        angle = config["angle"]
        start_numbers = config.get("start_numbers", None)  # Optional
        lat_increment = config["lat"]
        lon_increment = config["lon"]
        color = config.get("color", simplekml.Color.greenyellow)
        odd_row_offset = config.get("odd", 0)
        colored_numbers = config.get("colored_numbers", None)
        owned_colors = config.get("owned_colors", None)
        other_colors = config.get("other_colors", None)
        
        connections = [
            {544:["top_left", "top_right"],627: ["top_left", "top_right"],628: ["top_left", "top_right"],478:["top_right", "top_left"],428:["top_right","top_left"],427:["top_right","top_left"],},           
        ]
        extension_connections = [
            {386: ["bottom_right", "bottom_left"], 544: ["top_left", "bottom_right"]}
        ]

        survey_numbers = fetch_all_survey_numbers(connections)


        width = 161.957  # meters (grid cell width)
        height = 100  # meters (grid cell height)

        # Store the original starting coordinates for rotation
        original_start_lat, original_start_lon = start_lat, start_lon

        # Ensure start_numbers list is correct if provided
        if start_numbers and len(start_numbers) != rows:
            raise ValueError("The length of start_numbers must match the number of rows.")

        # Iterate over columns (left to right)
        for col in range(cols):
            current_lat, current_lon = start_lat, start_lon  # Reset lat/lon for each column

            # Iterate over rows (top to bottom)
            for row in range(rows):
                cell_number = start_numbers[row] + col if start_numbers else None  # Calculate cell number if provided

                # Calculate grid cell corners
                top_left = (current_lat, current_lon)
                top_right = geopy.distance.distance(meters=width).destination(top_left, 90)
                bottom_left = geopy.distance.distance(meters=height).destination(top_left, 180)
                bottom_right = geopy.distance.distance(meters=width).destination(bottom_left, 90)

                # Apply rotation to each corner
                rotated_top_left = rotate_point(top_left[0], top_left[1], angle, original_start_lat, original_start_lon)
                rotated_top_right = rotate_point(top_right[0], top_right[1], angle, original_start_lat, original_start_lon)
                rotated_bottom_left = rotate_point(bottom_left[0], bottom_left[1], angle, original_start_lat, original_start_lon)
                rotated_bottom_right = rotate_point(bottom_right[0], bottom_right[1], angle, original_start_lat, original_start_lon)

                # Create a polygon for the grid cell
                pol = kml.newpolygon()
                pol.outerboundaryis = [
                    (rotated_top_left[1], rotated_top_left[0]),  # Lon, Lat
                    (rotated_top_right[1], rotated_top_right[0]),
                    (rotated_bottom_right[1], rotated_bottom_right[0]),
                    (rotated_bottom_left[1], rotated_bottom_left[0]),
                    (rotated_top_left[1], rotated_top_left[0])  # Close the polygon
                ]
                
                pol.style.linestyle.color = color
                pol.style.linestyle.width = 3  # Line width

                # Add label to center of the grid cell if start_numbers is provided
                if start_numbers:
                    # Adjust the cell number based on row/column offset
                    if row % 2 == odd_row_offset:
                        cell_number = start_numbers[row] + (cols - 1 - col)
                    else:
                        cell_number = start_numbers[row] + col

                    # Define default fill and border colors
                    fill_color = 0  # Default no fill
                    border_color = simplekml.Color.changealphaint(100, simplekml.Color.blue)  # Default border (blue)

                    # Check if the cell number should be colored differently
                    if colored_numbers and cell_number in colored_numbers:
                        fill_color = 1 
                        border_color = simplekml.Color.changealphaint(100, simplekml.Color.blue)
                    elif owned_colors and cell_number in owned_colors:
                        fill_color = 1
                        border_color = simplekml.Color.changealphaint(100, simplekml.Color.red)
                   
                    # Apply fill and border styles to the polygon
                    pol.style.polystyle.fill = fill_color
                    pol.style.polystyle.color = border_color

                    # Compute the center coordinates for the label
                    center_lat = (rotated_top_left[0] + rotated_bottom_right[0]) / 2
                    center_lon = (rotated_top_left[1] + rotated_bottom_right[1]) / 2
                    pnt = kml.newpoint(coords=[(center_lon, center_lat)])
                    pnt.name = str(cell_number)
                    pnt.style.iconstyle.icon.href = ""  # No icon

                if cell_number in survey_numbers:
                    
                    # Store the coordinates of the cell
                    combined_coordinates[cell_number] = {
                        "top_left": rotated_top_left,
                        "bottom_left": rotated_bottom_left,
                        "top_right": rotated_top_right,
                        "bottom_right": rotated_bottom_right
                    }
                # Move to the next column (shift longitude)
                current_lon = geopy.distance.distance(meters=width).destination((current_lat, current_lon), lon_increment).longitude

            # Move to the next row (shift latitude)
            start_lat = geopy.distance.distance(meters=height).destination((start_lat, original_start_lon), lat_increment).latitude
            start_lon = original_start_lon  # Reset longitude for each row

        # Handle connections
    for conn in connections:
        coords = []  # List to store the coordinates for the polygon
        
        # Loop over the dictionary items in the connection
        for cell, corners in conn.items():
            if cell in combined_coordinates:
                # Get the corner coordinates for the cell
                cell_coords = combined_coordinates[cell]
                
                for corner in corners:
                    # Fetch the specific corner coordinates (latitude, longitude)
                    corner_coords = cell_coords.get(corner)
                    if corner_coords:
                        # Add the corner (longitude, latitude) to the coords list
                        coords.append((corner_coords[1], corner_coords[0]))  # (longitude, latitude)

        # Ensure the last coordinate connects to the first one to form a closed polygon
        if len(coords) > 2:
            coords.append(coords[0])  # Closing the polygon

            # Assuming you are using the KML library to create a polygon (simplekml or similar)
            pol = kml.newpolygon()
            pol.outerboundaryis = coords  # Set the polygon boundary to the list of coordinates
            pol.style.linestyle.color = simplekml.Color.red  # Example color for the polygon border
            pol.style.linestyle.width = 3  # Line width
            pol.style.polystyle.fill = 0  # No fill

            
    # Save the KML file and open it
    kml.save(output_filename)
    print(f"KML file '{output_filename}' generated successfully.")
    webbrowser.open(f"file://{os.path.realpath(output_filename)}")  # Open the KML file in browser


# Example usage:
grid_configs = [
    {
        "start_lat": 23.915223, "start_lon": 67.241031, "rows": 11, "cols": 23, "angle": 91.5,
        "start_numbers": [479, 456, 428, 405, 386, 364, 347, 321, 306,287,272], "lat": 180, "lon": 270,             
        "colored_numbers": [479, 456, 428, 405, 386, 364, 347, 321, 306,287,272], "owned_colors": [479], "odd": 1,
        "color": simplekml.Color.yellow,
    },
]

# Call the function with all grid configurations
generate_grids_kml(grid_configs, output_filename="multiple_grids.kml")