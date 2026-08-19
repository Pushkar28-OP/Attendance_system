import math
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.services.location_service import verify_location
from app.utils.distance import haversine_distance_meters


def test_password_hashing_and_jwt():
    password = "CorrectHorseBatteryStaple"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    claims = decode_access_token(create_access_token("EMP-1", "employee"))
    assert claims["sub"] == "EMP-1"
    assert claims["role"] == "employee"


def test_haversine_distance_zero_and_known_distance():
    assert haversine_distance_meters(0, 0, 0, 0) == 0
    assert math.isclose(haversine_distance_meters(0, 0, 0, 0.001), 111.2, rel_tol=0.02)


def test_geofence_rejects_unconfigured_office(monkeypatch):
    from types import SimpleNamespace
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.delenv("OFFICE_LATITUDE", raising=False)
    monkeypatch.delenv("OFFICE_LONGITUDE", raising=False)
    monkeypatch.setattr("app.services.location_service.get_settings", lambda: SimpleNamespace(office_latitude=None, office_longitude=None, office_radius_meters=150))
    ok, distance, reason = verify_location(1, 1, 10)
    assert not ok
    assert distance is None
    assert reason == "OFFICE_LOCATION_NOT_CONFIGURED"
