from .face_service import face_service


def verify_liveness(frames: list[str], primary_embedding: list[float]) -> tuple[bool, float]:
    """MVP liveness: require multiple frames with a consistent face and measurable movement."""
    if len(frames) < 2:
        return False, 0.0
    embeddings = []
    for frame in frames[:8]:
        try:
            embeddings.append(face_service.extract(frame).embedding)
        except (ValueError, RuntimeError):
            return False, 0.0
    scores = [face_service.similarity(primary_embedding, embedding) for embedding in embeddings]
    if not scores or min(scores) < 0.65:
        return False, 0.0
    movement = max(scores) - min(scores)
    liveness_score = min(1.0, 0.65 + movement * 4.0)
    return movement >= 0.008, liveness_score
