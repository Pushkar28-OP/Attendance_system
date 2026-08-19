from app.core.config import get_settings
from app.utils.distance import haversine_distance_meters


def verify_location(latitude: float, longitude: float, accuracy: float) -> tuple[bool, float | None, str | None]:
    settings = get_settings()
    if settings.office_latitude is None or settings.office_longitude is None:
        return False, None, "OFFICE_LOCATION_NOT_CONFIGURED"
    if accuracy > max(settings.office_radius_meters, 100):
        return False, None, "LOCATION_ACCURACY_INSUFFICIENT"
    distance = haversine_distance_meters(latitude, longitude, settings.office_latitude, settings.office_longitude)
    if distance > settings.office_radius_meters:
        return False, distance, "LOCATION_OUTSIDE_GEOFENCE"
    return True, distance, None
