from datetime import datetime, timezone


def audit_event(event_type: str, actor_id: str | None, result: str, metadata: dict | None = None) -> dict:
    return {"event_type": event_type, "actor_id": actor_id, "result": result, "metadata": metadata or {}, "created_at": datetime.now(timezone.utc)}
