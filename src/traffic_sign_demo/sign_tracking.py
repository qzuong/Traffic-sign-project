from __future__ import annotations

from dataclasses import dataclass, replace

import cv2
import numpy as np

from .vision import ClassifiedDetection, DisplayFrame, clip_bbox


@dataclass(frozen=True)
class _Track:
    detection: ClassifiedDetection
    reference: np.ndarray
    anchored_ms: float
    box: tuple[int, int, int, int]


def _overlap(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    return intersection / (
        (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    )


class SignTracker:
    """Follow recently classified signs using local image matches."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._tracks: list[_Track] = []
        self._previous: tuple[int, int, float] | None = None

    def update(
        self, frame: DisplayFrame, detections: tuple[ClassifiedDetection, ...]
    ) -> tuple[ClassifiedDetection, ...]:
        height, width = frame.image.shape[:2]
        scale_x, scale_y = width / frame.source_width, height / frame.source_height
        scale = (scale_x, scale_y, scale_x, scale_y)
        previous = self._previous
        gap = 0.0 if previous is None else frame.timestamp_ms - previous[2]
        if previous is None or previous[0] != frame.session_id or not 0 <= gap <= 200:
            self._tracks.clear()
        elif gap:
            self._tracks = [
                updated for track in self._tracks
                if frame.timestamp_ms - track.anchored_ms <= 350
                and (updated := self._match(frame.image, track)) is not None
            ]
        elif previous[1] != frame.frame_id:
            self._tracks.clear()

        self._previous = frame.session_id, frame.frame_id, frame.timestamp_ms
        current: list[_Track] = []
        for detection in detections:
            box = clip_bbox(tuple(a * b for a, b in zip(detection.bbox, scale)), width, height)
            if box is None:
                continue
            self._tracks = [track for track in self._tracks if _overlap(track.box, box) < 0.3]
            x, y, right, bottom = box
            if min(right - x, bottom - y) < 8:
                continue
            reference = cv2.cvtColor(frame.image[y:bottom, x:right], cv2.COLOR_BGR2GRAY)
            if reference.std() >= 12:
                current.append(_Track(detection, reference, frame.timestamp_ms, box))

        carried = tuple(
            replace(track.detection, bbox=tuple(value / factor for value, factor in zip(track.box, scale)))
            for track in self._tracks
        )
        self._tracks = (current + self._tracks)[:8]
        return detections + carried

    @staticmethod
    def _match(image: np.ndarray, track: _Track) -> _Track | None:
        x, y, right, bottom = track.box
        width, height = right - x, bottom - y
        radius = min(48, max(8, round(max(width, height) * 0.55)))
        top, left = max(0, y - radius), max(0, x - radius)
        region = image[top:bottom + radius, left:right + radius]
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        best_score, best_box = 0.88, None
        for ratio in (1.0, 0.9, 1.1):
            w, h = round(width * ratio), round(height * ratio)
            if not (6 <= w <= gray.shape[1] and 6 <= h <= gray.shape[0]):
                continue
            template = cv2.resize(track.reference, (w, h))
            matches = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, score, _, (dx, dy) = cv2.minMaxLoc(matches)
            if score >= best_score:
                best_score = score
                best_box = (left + dx, top + dy, left + dx + w, top + dy + h)
        if best_box is None:
            return None
        limit_width, limit_height = image.shape[1], image.shape[0]
        if best_box[0] == 0 or best_box[1] == 0 or best_box[2] == limit_width or best_box[3] == limit_height:
            return None
        return replace(track, box=best_box)
