from math import asin, cos, radians, sin, sqrt


def haversine_distance_meters(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    earth_radius = 6_371_000
    delta_lat = radians(latitude_b - latitude_a)
    delta_lon = radians(longitude_b - longitude_a)
    value = sin(delta_lat / 2) ** 2 + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(delta_lon / 2) ** 2
    return 2 * earth_radius * asin(sqrt(value))
