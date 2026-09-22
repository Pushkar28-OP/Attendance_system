from functools import lru_cache
import logging

import httpx

from app.core.config import get_settings


logger = logging.getLogger(__name__)


def _first_value(address: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = address.get(key)
        if value:
            return str(value)
    return None


def _google_components(components: list[dict]) -> dict[str, str]:
    values = {}
    for component in components:
        for component_type in component.get("types", []):
            values.setdefault(component_type, component.get("long_name"))
    area = _first_value(values, ("neighborhood", "sublocality_level_2", "sublocality_level_1", "sublocality", "route"))
    city = _first_value(values, ("locality", "postal_town", "administrative_area_level_2"))
    return {"area": area, "city": city} if area or city else {}


def _reverse_geocode_google(latitude: float, longitude: float, settings) -> dict[str, str] | None:
    response = httpx.get(
        settings.google_geocode_url,
        params={"latlng": f"{latitude},{longitude}", "key": settings.google_maps_api_key},
        timeout=settings.reverse_geocode_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "OK" or not payload.get("results"):
        return None
    result = payload["results"][0]
    location = _google_components(result.get("address_components", []))
    formatted_address = result.get("formatted_address")
    if not formatted_address:
        return None
    area = location.get("area")
    city = location.get("city")
    location["display_name"] = ", ".join(part for part in (area, city) if part) or formatted_address
    location["formatted_address"] = formatted_address
    return location


@lru_cache(maxsize=512)
def reverse_geocode_location(latitude: float, longitude: float) -> dict[str, str] | None:
    settings = get_settings()
    try:
        if settings.google_maps_api_key:
            try:
                google_location = _reverse_geocode_google(latitude, longitude, settings)
                if google_location:
                    return google_location
            except Exception:
                logger.warning("Google reverse geocoding failed for %.6f, %.6f; trying Nominatim", latitude, longitude, exc_info=True)
        fallback = None
        for zoom in (18, 14):
            response = httpx.get(
                settings.reverse_geocode_url,
                params={"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": zoom, "addressdetails": 1},
                headers={"User-Agent": settings.reverse_geocode_user_agent},
                timeout=settings.reverse_geocode_timeout_seconds,
            )
            response.raise_for_status()
            address = response.json().get("address", {})
            locality = _first_value(address, ("neighbourhood", "suburb", "city_district", "locality", "sublocality", "residential", "road"))
            city = _first_value(address, ("city", "town", "municipality"))
            state = address.get("state")
            if locality:
                display_name = ", ".join(dict.fromkeys(part for part in (locality, city) if part))
                return {"area": locality, "city": city, "display_name": display_name}
            if city and fallback is None:
                display_name = ", ".join(dict.fromkeys(part for part in (city, state) if part))
                fallback = {"area": city, "city": city, "display_name": display_name}
            elif state and fallback is None:
                fallback = {"area": state, "display_name": state}
        return fallback
    except Exception:
        logger.warning("Reverse geocoding failed for %.6f, %.6f", latitude, longitude, exc_info=True)
        return None