from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import attendance_service
from app.services import geocoding_service
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.attendance import public_attendance


def test_password_hashing_and_jwt():
    password = "CorrectHorseBatteryStaple"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    claims = decode_access_token(create_access_token("EMP-1", "employee"))
    assert claims["sub"] == "EMP-1"
    assert claims["role"] == "employee"


class FakeCollection:
    def __init__(self, document=None):
        self.document = document
        self.updated = None
        self.inserted = None

    def find_one(self, _query):
        return self.document

    def update_one(self, _query, update):
        self.updated = update["$set"]
        self.document.update(self.updated)

    def insert_one(self, document):
        self.inserted = document
        document.setdefault("_id", "record-1")
        self.document = document


class FakeDb:
    def __init__(self, document):
        self.attendance = FakeCollection(document)
        self.audit_logs = FakeCollection()


class FailingAuditCollection:
    def insert_one(self, _document):
        raise RuntimeError("audit collection unavailable")


def test_check_in_updates_check_in_fields_for_existing_empty_record(monkeypatch):
    existing = {
        "_id": "record-1",
        "attendance_id": "attendance-1",
        "employee_id": "EMP-1",
        "date": "2026-09-22",
        "check_in_time": None,
        "check_out_time": None,
        "final_status": "ABSENT",
    }
    fake_db = FakeDb(existing)
    monkeypatch.setattr(attendance_service, "get_db", lambda: fake_db)

    result = attendance_service.verify_and_record(
        {"employee_id": "EMP-1", "full_name": "Test Employee"},
        SimpleNamespace(action="check_in", latitude=None, longitude=None, accuracy=None),
    )

    assert result["success"] is True
    assert fake_db.attendance.updated["check_in_time"] is not None
    assert fake_db.attendance.updated["check_out_time"] is None


def test_check_in_and_check_out_store_the_submitted_locations(monkeypatch):
    fake_db = FakeDb(None)
    monkeypatch.setattr(attendance_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(attendance_service, "reverse_geocode_location", lambda latitude, longitude: {"area": "Baner", "city": "Pune"})
    employee = {"employee_id": "EMP-1", "full_name": "Test Employee"}

    check_in = SimpleNamespace(action="check_in", latitude=18.5204, longitude=73.8567, accuracy=12.5)
    check_out = SimpleNamespace(action="check_out", latitude=18.5210, longitude=73.8572, accuracy=18.0)

    assert attendance_service.verify_and_record(employee, check_in)["success"] is True
    assert fake_db.attendance.document["check_in_location"] == {"latitude": 18.5204, "longitude": 73.8567, "accuracy": 12.5, "source": "browser", "area": "Baner", "city": "Pune"}
    assert attendance_service.verify_and_record(employee, check_out)["success"] is True
    assert fake_db.attendance.document["check_out_location"] == {"latitude": 18.5210, "longitude": 73.8572, "accuracy": 18.0, "source": "browser", "area": "Baner", "city": "Pune"}


def test_reverse_geocoding_failure_keeps_attendance_working(monkeypatch):
    fake_db = FakeDb(None)
    monkeypatch.setattr(attendance_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(attendance_service, "reverse_geocode_location", lambda latitude, longitude: None)

    result = attendance_service.verify_and_record(
        {"employee_id": "EMP-1", "full_name": "Test Employee"},
        SimpleNamespace(action="check_in", latitude=18.5204, longitude=73.8567, accuracy=10.0),
    )

    assert result["success"] is True
    assert fake_db.attendance.document["check_in_location"] == {"latitude": 18.5204, "longitude": 73.8567, "accuracy": 10.0, "source": "browser"}


def test_reverse_geocoding_returns_concise_area_and_uses_cache(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"address": {"suburb": "Baner", "city": "Pune", "state": "Maharashtra"}}

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setattr(geocoding_service.httpx, "get", fake_get)
    geocoding_service.reverse_geocode_location.cache_clear()

    assert geocoding_service.reverse_geocode_location(18.5590, 73.7898) == {"area": "Baner", "city": "Pune", "display_name": "Baner, Pune"}
    assert geocoding_service.reverse_geocode_location(18.5590, 73.7898) == {"area": "Baner", "city": "Pune", "display_name": "Baner, Pune"}
    assert len(calls) == 1


def test_google_reverse_geocoding_uses_formatted_address_and_components(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "OK",
                "results": [{
                    "formatted_address": "Law College Road, Erandwane, Pune, Maharashtra, India",
                    "address_components": [
                        {"long_name": "Law College Road", "types": ["route"]},
                        {"long_name": "Erandwane", "types": ["sublocality_level_1"]},
                        {"long_name": "Pune", "types": ["locality"]},
                    ],
                }],
            }

    monkeypatch.setattr(geocoding_service.httpx, "get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(geocoding_service, "get_settings", lambda: SimpleNamespace(
        google_maps_api_key="test-key",
        google_geocode_url="https://maps.googleapis.com/maps/api/geocode/json",
        reverse_geocode_timeout_seconds=3.0,
    ))
    geocoding_service.reverse_geocode_location.cache_clear()

    assert geocoding_service.reverse_geocode_location(18.51, 73.83) == {
        "area": "Erandwane",
        "city": "Pune",
        "display_name": "Erandwane, Pune",
        "formatted_address": "Law College Road, Erandwane, Pune, Maharashtra, India",
    }


def test_reverse_geocoding_uses_city_and_state_without_locality(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"address": {"city": "Pune", "state": "Maharashtra"}}

    monkeypatch.setattr(geocoding_service.httpx, "get", lambda *args, **kwargs: FakeResponse())
    geocoding_service.reverse_geocode_location.cache_clear()

    assert geocoding_service.reverse_geocode_location(18.5204, 73.8567) == {"area": "Pune", "city": "Pune", "display_name": "Pune, Maharashtra"}


def test_reverse_geocoding_retries_at_locality_zoom(monkeypatch):
    responses = iter([
        {"address": {"city": "Pune", "state": "Maharashtra"}},
        {"address": {"suburb": "Keshav Nagar", "city": "Pune", "state": "Maharashtra"}},
    ])

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return next(responses)

    monkeypatch.setattr(geocoding_service.httpx, "get", lambda *args, **kwargs: FakeResponse())
    geocoding_service.reverse_geocode_location.cache_clear()

    assert geocoding_service.reverse_geocode_location(18.501528, 73.943451) == {"area": "Keshav Nagar", "city": "Pune", "display_name": "Keshav Nagar, Pune"}


def test_public_attendance_normalizes_legacy_naive_mongo_timestamps_to_utc():
    record = public_attendance({
        "attendance_id": "attendance-1",
        "employee_id": "EMP-1",
        "date": "2026-09-22",
        "check_in_time": datetime(2026, 9, 22, 11, 28, 4),
        "check_out_time": None,
        "check_in_location": None,
        "check_out_location": None,
        "final_status": "PRESENT",
    })

    assert record["check_in_time"].tzinfo == timezone.utc
    assert record["check_in_time"].isoformat() == "2026-09-22T11:28:04+00:00"


def test_audit_failure_does_not_turn_a_recorded_check_in_into_a_server_error(monkeypatch):
    fake_db = FakeDb(None)
    fake_db.audit_logs = FailingAuditCollection()
    monkeypatch.setattr(attendance_service, "get_db", lambda: fake_db)
    monkeypatch.setattr(attendance_service, "reverse_geocode_location", lambda latitude, longitude: None)

    result = attendance_service.verify_and_record(
        {"employee_id": "EMP-1", "full_name": "Test Employee"},
        SimpleNamespace(action="check_in", latitude=18.5204, longitude=73.8567, accuracy=10.0),
    )

    assert result["success"] is True
    assert fake_db.attendance.document["check_in_location"] == {"latitude": 18.5204, "longitude": 73.8567, "accuracy": 10.0, "source": "browser"}
