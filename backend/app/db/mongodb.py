from datetime import timezone

from pymongo import ASCENDING, DESCENDING, MongoClient
from app.core.config import get_settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(get_settings().mongodb_uri, serverSelectionTimeoutMS=3000, tz_aware=True, tzinfo=timezone.utc)
    return _client


def get_db():
    return get_client()[get_settings().database_name]


def init_indexes() -> None:
    db = get_db()
    db.employees.create_index("employee_id", unique=True)
    db.employees.create_index("email", unique=True)
    db.attendance.create_index([("employee_id", ASCENDING), ("date", DESCENDING)])
    db.attendance.create_index([("employee_id", ASCENDING), ("date", ASCENDING)], unique=True)
    db.audit_logs.create_index([("created_at", DESCENDING)])
