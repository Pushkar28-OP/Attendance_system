import base64
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class FaceResult:
    embedding: list[float]
    quality_score: float


class FaceService:
    def __init__(self):
        self._app = None
        self._load_error: Exception | None = None

    def _model(self):
        if self._app is None and self._load_error is None:
            try:
                from insightface.app import FaceAnalysis
                self._app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                self._app.prepare(ctx_id=0, det_size=(640, 640))
            except Exception as exc:
                self._load_error = exc
        if self._load_error:
            raise RuntimeError("Face recognition service is unavailable") from self._load_error
        return self._app

    @staticmethod
    def _decode(image: str) -> np.ndarray:
        payload = image.split(",", 1)[-1]
        try:
            raw = base64.b64decode(payload, validate=True)
            array = np.frombuffer(raw, dtype=np.uint8)
            frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
        except Exception as exc:
            raise ValueError("Invalid camera image") from exc
        if frame is None:
            raise ValueError("Invalid camera image")
        return frame

    def extract(self, image: str) -> FaceResult:
        frame = self._decode(image)
        height, width = frame.shape[:2]
        if min(height, width) < 160:
            raise ValueError("Camera image quality is insufficient")
        faces = self._model().get(frame)
        if len(faces) != 1:
            raise ValueError("Exactly one face must be visible")
        face = faces[0]
        box = face.bbox
        face_width = max(0.0, float(box[2] - box[0]))
        face_height = max(0.0, float(box[3] - box[1]))
        area_ratio = (face_width * face_height) / (width * height)
        if area_ratio < 0.04:
            raise ValueError("Please move closer to the camera")
        quality = min(1.0, area_ratio * 4.0)
        embedding = np.asarray(face.normed_embedding, dtype=np.float32)
        return FaceResult(embedding=embedding.tolist(), quality_score=quality)

    @staticmethod
    def similarity(first: list[float], second: list[float]) -> float:
        left = np.asarray(first, dtype=np.float32)
        right = np.asarray(second, dtype=np.float32)
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        if denominator == 0:
            return 0.0
        return float(np.dot(left, right) / denominator)


face_service = FaceService()
