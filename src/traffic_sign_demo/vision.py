from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .vietnamese_labels import VIETNAMESE_CLASSES


@dataclass(frozen=True)
class ClassifiedDetection:
    bbox: tuple[float, float, float, float]
    yolo_class_id: int
    yolo_class_name: str
    yolo_confidence: float
    cnn_class_id: int
    cnn_class_name: str
    cnn_score: float
    valid_yolo_at: float | None = field(default=None, compare=False)
    valid_cnn_at: float | None = field(default=None, compare=False)
    speech_veto: str | None = field(default=None, compare=False)


@dataclass(frozen=True)
class InferenceResult:
    session_id: int
    frame_id: int
    timestamp_ms: float
    submitted_monotonic: float
    completed_monotonic: float
    elapsed_ms: float
    detections: tuple[ClassifiedDetection, ...]
    stage_ms: dict[str, float] = field(default_factory=dict)

    @property
    def generation(self) -> int:
        return self.session_id


@dataclass(frozen=True)
class DisplayFrame:
    session_id: int
    frame_id: int
    timestamp_ms: float
    source_width: int
    source_height: int
    image: np.ndarray


def clip_bbox(
    bbox: object, frame_width: int, frame_height: int
) -> tuple[int, int, int, int] | None:
    if isinstance(bbox, np.ndarray):
        if bbox.ndim != 1 or bbox.size != 4:
            return None
    elif not isinstance(bbox, (tuple, list)) or len(bbox) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
        return None
    if frame_width <= 0 or frame_height <= 0:
        return None

    left = max(0, min(frame_width, math.floor(x1)))
    top = max(0, min(frame_height, math.floor(y1)))
    right = max(0, min(frame_width, math.ceil(x2)))
    bottom = max(0, min(frame_height, math.ceil(y2)))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def preprocess_crop(crop: np.ndarray) -> np.ndarray:
    if (
        not isinstance(crop, np.ndarray)
        or crop.ndim != 3
        or crop.shape[2] != 3
        or crop.shape[0] == 0
        or crop.shape[1] == 0
    ):
        raise ValueError("A non-empty BGR image crop is required.")

    resized = cv2.resize(crop, (30, 30))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    return normalized[np.newaxis, ...]


@lru_cache(maxsize=16)
def _label_font(size: int):
    for family in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(family, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


@lru_cache(maxsize=128)
def _label_bitmap(text: str, font_size: int, max_width: int) -> np.ndarray | None:
    padding = 6
    for size in range(font_size, 11, -1):
        font = _label_font(size)
        left, top, right, bottom = font.getbbox(text)
        width = right - left + 2 * padding
        if width <= max_width:
            image = Image.new("L", (width, bottom - top + 2 * padding), 20)
            ImageDraw.Draw(image).text((padding - left, padding - top), text, fill=255, font=font)
            return cv2.cvtColor(np.asarray(image), cv2.COLOR_GRAY2BGR)
    return None


def draw_overlay(
    display_frame: np.ndarray,
    detections: tuple[ClassifiedDetection, ...],
    source_width: int,
    source_height: int,
) -> np.ndarray:
    annotated = display_frame.copy()
    display_height, display_width = annotated.shape[:2]
    scale_x = display_width / source_width
    scale_y = display_height / source_height
    boxes = []
    for detection in detections:
        box = clip_bbox(detection.bbox, source_width, source_height)
        if box is None:
            continue
        x1, y1, x2, y2 = (
            min(display_width - 1, round(box[0] * scale_x)),
            min(display_height - 1, round(box[1] * scale_y)),
            min(display_width - 1, round(box[2] * scale_x)),
            min(display_height - 1, round(box[3] * scale_y)),
        )
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (40, 220, 40), 3)
        boxes.append(((x1, y1, x2, y2), detection.cnn_class_id))

    occupied = [(x1 - 2, y1 - 2, x2 + 3, y2 + 3) for (x1, y1, x2, y2), _ in boxes]
    font_size = min(26, max(18, round(display_width * 0.026)))
    for (x1, y1, x2, y2), class_id in boxes:
        label = _label_bitmap(
            VIETNAMESE_CLASSES.get(class_id, "Biển báo giao thông"), font_size, display_width
        )
        if label is None:
            continue
        height, width = label.shape[:2]
        aligned = min(x1, display_width - width)
        for x, y in ((aligned, y1 - height - 5), (aligned, y2 + 5),
                     (x2 + 5, y1), (x1 - width - 5, y1)):
            if x < 0 or y < 0 or x + width > display_width or y + height > display_height:
                continue
            if any(x < r and x + width > l and y < b and y + height > t for l, t, r, b in occupied):
                continue
            annotated[y:y + height, x:x + width] = label
            occupied.append((x, y, x + width, y + height))
            break
    return annotated


def overlay_rejection_reason(
    result: InferenceResult,
    session_id: int,
    frame_id: int,
    timestamp_ms: float,
    now_monotonic: float,
    max_age_ms: float,
) -> str | None:
    if result.session_id != session_id:
        return "different playback session"
    if result.frame_id != frame_id:
        return "different frame"
    if not math.isclose(result.timestamp_ms, timestamp_ms, rel_tol=0.0, abs_tol=0.001):
        return "different video timestamp"
    age_ms = (now_monotonic - result.submitted_monotonic) * 1000.0
    if age_ms < 0:
        return "completion timestamp is in the future"
    if age_ms > max_age_ms:
        return f"expired ({age_ms:.0f} ms old)"
    return None
