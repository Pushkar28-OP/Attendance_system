from datetime import datetime, timedelta, timezone
from io import BytesIO
from threading import Lock
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, UploadFile
from gridfs import GridFSBucket
from gridfs.errors import NoFile
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.db.mongodb import get_db


MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_EDGE = 1920
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
PENDING_ATTENDANCE_ID = "pending"
PHOTO_EVENTS = ("check_in", "check_out")
PHOTO_REFERENCE_FIELDS = ("check_in_photo_reference", "check_out_photo_reference")

_cleanup_lock = Lock()


class PhotoExpiredError(Exception):
    """Raised when a stored attendance photo has passed its retention window."""


def photo_retention() -> timedelta:
    return timedelta(hours=get_settings().photo_retention_hours)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def photo_is_expired(expires_at, now: datetime | None = None) -> bool:
    expiry = _as_utc(expires_at)
    if expiry is None:
        return False
    return expiry <= (now or _utc_now())


def reference_is_expired(reference: dict | None, now: datetime | None = None) -> bool:
    if not reference:
        return True
    return photo_is_expired(reference.get("expires_at"), now)


async def prepare_photo(upload: UploadFile) -> tuple[bytes, str]:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Photo must be a JPEG, PNG, or WebP image")
    data = await upload.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo must be 8 MB or smaller")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            normalized = image.convert("RGB")
            if max(normalized.size) > MAX_PHOTO_EDGE:
                normalized.thumbnail((MAX_PHOTO_EDGE, MAX_PHOTO_EDGE), Image.Resampling.LANCZOS)
            output = BytesIO()
            normalized.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue(), "image/jpeg"
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid image") from exc


def store_photo(data: bytes, content_type: str, employee_id: str, attendance_id: str, event: str) -> dict:
    uploaded_at = _utc_now()
    expires_at = uploaded_at + photo_retention()
    bucket = GridFSBucket(get_db())
    photo_id = bucket.upload_from_stream(
        f"attendance-{event}-{uuid4()}.jpg",
        BytesIO(data),
        metadata={
            "employee_id": employee_id,
            "attendance_id": attendance_id,
            "event": event,
            "content_type": content_type,
            "uploaded_at": uploaded_at,
            "expires_at": expires_at,
        },
    )
    return {"file_id": str(photo_id), "content_type": content_type, "expires_at": expires_at}


def bind_photo_to_attendance(reference: dict | None, attendance_id: str) -> None:
    if not reference or not reference.get("file_id") or not attendance_id:
        return
    get_db().fs.files.update_one(
        {"_id": ObjectId(reference["file_id"])},
        {"$set": {"metadata.attendance_id": attendance_id}},
    )


def _purge_gridfs_file(db, file_id: ObjectId) -> None:
    try:
        GridFSBucket(db).delete(file_id)
    except Exception:
        db.fs.files.delete_one({"_id": file_id})
        db.fs.chunks.delete_many({"files_id": file_id})


def delete_photo(reference: dict | None) -> None:
    if not reference or not reference.get("file_id"):
        return
    try:
        file_id = ObjectId(reference["file_id"])
    except Exception:
        return
    _purge_gridfs_file(get_db(), file_id)


def open_photo(reference: dict):
    file_id = ObjectId(reference["file_id"])
    try:
        stream = GridFSBucket(get_db()).open_download_stream(file_id)
    except NoFile as exc:
        raise PhotoExpiredError("Photo expired or unavailable") from exc
    metadata = stream.metadata or {}
    expires_at = metadata.get("expires_at") or reference.get("expires_at")
    if photo_is_expired(expires_at):
        raise PhotoExpiredError("Photo expired or unavailable")
    return stream


def _file_is_expired(file_doc: dict, now: datetime) -> bool:
    metadata = file_doc.get("metadata") or {}
    if photo_is_expired(metadata.get("expires_at"), now):
        return True
    if metadata.get("expires_at") is None:
        uploaded = _as_utc(file_doc.get("uploadDate")) or _as_utc(metadata.get("uploaded_at"))
        return bool(uploaded and uploaded + photo_retention() <= now)
    return False


def _clear_expired_attendance_references(db, now: datetime) -> int:
    cleared = 0
    for field in PHOTO_REFERENCE_FIELDS:
        for record in db.attendance.find({field: {"$ne": None}}):
            reference = record.get(field) or {}
            file_id_raw = reference.get("file_id")
            missing = True
            expired = reference_is_expired(reference, now)
            if file_id_raw:
                try:
                    file_doc = db.fs.files.find_one({"_id": ObjectId(file_id_raw)})
                except Exception:
                    file_doc = None
                missing = file_doc is None
                expired = expired or (file_doc is not None and _file_is_expired(file_doc, now))
            if missing or expired:
                db.attendance.update_one({"_id": record["_id"]}, {"$set": {field: None, "updated_at": now}})
                cleared += 1
    return cleared


def cleanup_expired_photos() -> dict:
    with _cleanup_lock:
        db = get_db()
        now = _utc_now()
        deleted_files = 0
        query = {"metadata.event": {"$in": list(PHOTO_EVENTS)}}
        for file_doc in list(db.fs.files.find(query)):
            if not _file_is_expired(file_doc, now):
                continue
            _purge_gridfs_file(db, file_doc["_id"])
            deleted_files += 1
        cleared_references = _clear_expired_attendance_references(db, now)
        return {"deleted_files": deleted_files, "cleared_references": cleared_references}
