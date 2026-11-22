"""Conservative sign identities for voice alerts on displayed detection frames."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import math

import cv2
import numpy as np

from .vietnamese_labels import VIETNAMESE_CLASSES
from .vision import ClassifiedDetection, DisplayFrame, clip_bbox

MAX_TRACK_GAP_MS = 900
_VOTE_WINDOW_MS = 1300


def _centre(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    return intersection / (
        (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    )


def _appearance(image, box):
    x, y, r, b = box
    gray = cv2.cvtColor(image[y:b, x:r], cv2.COLOR_BGR2GRAY)
    patch = cv2.resize(gray, (20, 20), interpolation=cv2.INTER_AREA).astype(np.float32)
    patch -= patch.mean()
    norm = np.linalg.norm(patch)
    return patch / norm if norm >= 120 else None


@dataclass
class AlertTrack:
    id: int
    box: tuple[int, int, int, int]
    appearance: np.ndarray | None
    last_ms: float
    first_seen: float
    first_yolo_at: float
    first_cnn_at: float | None = None
    velocity: tuple[float, float] = (0, 0)
    votes: deque[tuple[float, int, float, str | None]] = field(default_factory=lambda: deque(maxlen=5))
    confirmed: int | None = None
    speech_block: str | None = None
    speech_suppressions: set[tuple[int, str]] = field(default_factory=set)
    offered: bool = False
    simulation_session: str | None = None

    @property
    def speech_class(self) -> int | None:
        return self.confirmed if self.speech_block is None else None

    def score(self, box, appearance, timestamp):
        gap = timestamp - self.last_ms
        x, y, r, b = self.box
        width, height = r - x, b - y
        if not 0.45 <= (box[2] - box[0]) * (box[3] - box[1]) / (width * height) <= 2.8:
            return None
        dx, dy = (max(-2 * width, min(2 * width, speed * gap)) for speed in self.velocity)
        forecast = x + dx, y + dy, r + dx, b + dy
        overlap = max(_iou(forecast, box), _iou(self.box, box))
        cx, cy = _centre(box)
        px, py = _centre(forecast)
        distance = math.hypot(cx - px, cy - py)
        radius = min(82, max(22, 1.7 * max(width, height)))
        if appearance is None or self.appearance is None:
            return overlap if overlap >= 0.48 and gap <= 350 else None
        if distance > radius and overlap < 0.25:
            return None
        similarity = float(np.sum(self.appearance * appearance))
        if similarity < -0.25:
            return None
        # A small detection's crop can jitter a few pixels without the sign moving.
        if similarity < 0.68 and gap <= 450:
            core = self.appearance[2:-2, 2:-2]
            similarity = max(similarity, float(cv2.matchTemplate(
                appearance, core, cv2.TM_CCOEFF_NORMED
            ).max()))
        if similarity < (0.62 if gap > 450 else 0.45):
            return None
        return 0.42 * overlap + 0.43 * similarity + 0.15 * max(0, 1 - distance / radius)

    def record(self, box, appearance, detection, timestamp, minimum, now):
        if timestamp > self.last_ms:
            x, y = _centre(self.box)
            nx, ny = _centre(box)
            gap = timestamp - self.last_ms
            self.velocity = (nx - x) / gap, (ny - y) / gap
        self.box, self.appearance, self.last_ms = box, appearance, timestamp
        class_id, score = detection.cnn_class_id, detection.cnn_score
        if class_id not in VIETNAMESE_CLASSES or not math.isfinite(score) or not 0 <= score <= 1:
            self.speech_block = "invalid_latest_prediction"
            return
        if self.first_cnn_at is None:
            self.first_cnn_at = detection.valid_cnn_at if detection.valid_cnn_at is not None else now
        while self.votes and timestamp - self.votes[0][0] > _VOTE_WINDOW_MS:
            self.votes.popleft()
        self.votes.append((timestamp, class_id, score, detection.speech_veto))
        weights, counts, eligible_counts = defaultdict(float), defaultdict(int), defaultdict(int)
        for _, label, confidence, veto in self.votes:
            weights[label] += confidence
            counts[label] += 1
            if veto is None and confidence > 0:
                eligible_counts[label] += 1
        winner = max(weights, key=weights.get)
        self.confirmed = (
            winner if counts[winner] >= minimum and weights[winner] > 0
            and weights[winner] >= 0.65 * sum(weights.values()) else None
        )
        self.speech_block = detection.speech_veto
        if self.speech_block is None and self.confirmed is not None:
            if class_id != self.confirmed:
                self.speech_block = "latest_prediction_disagrees"
            elif eligible_counts[self.confirmed] < minimum:
                self.speech_block = "insufficient_eligible_observations"


class AlertTracks:
    def __init__(self, min_observations: int = 2) -> None:
        if not 2 <= min_observations <= 5:
            raise ValueError("Confirmation requires between two and five observations.")
        self.min_observations = min_observations
        self.active: dict[int, AlertTrack] = {}
        self.created = 0
        self.lost = 0
        self.ambiguous = 0
        self.unresolved_associations = 0
        self.unconfirmed_lost = 0
        self._last_observation_ms = -1.0

    def update(self, frame: DisplayFrame, detections: tuple[ClassifiedDetection, ...], now: float):
        timestamp = frame.timestamp_ms
        for track_id, track in tuple(self.active.items()):
            if timestamp - track.last_ms > MAX_TRACK_GAP_MS:
                del self.active[track_id]
                self.lost += 1
                self.unconfirmed_lost += not track.offered
        if not detections or timestamp <= self._last_observation_ms:
            return []
        self._last_observation_ms = timestamp
        height, width = frame.image.shape[:2]
        scale = (width / frame.source_width, height / frame.source_height) * 2
        observations = []
        for detection in detections[:32]:
            box = clip_bbox(tuple(c * s for c, s in zip(detection.bbox, scale)), width, height)
            if box is not None:
                observations.append((detection, box, _appearance(frame.image, box)))

        pairs = [
            (score, track.id, i)
            for i, (_, box, patch) in enumerate(observations)
            for track in self.active.values()
            if (score := track.score(box, patch, timestamp)) is not None
        ]
        paired = {}
        uncertain = set()
        for score, track_id, index in sorted(pairs, reverse=True):
            if index in paired or track_id in paired.values():
                continue
            if any((other_id == track_id or other_index == index)
                   and (other_id, other_index) != (track_id, index)
                   and abs(score - other_score) < 0.075
                   for other_score, other_id, other_index in pairs):
                self.ambiguous += 1
                uncertain.add(index)
                continue
            paired[index] = track_id
        self.unresolved_associations += len(uncertain.difference(paired))

        seen = []
        for i, (detection, box, patch) in enumerate(observations):
            if i in paired:
                track = self.active[paired[i]]
            else:
                self.created += 1
                track = AlertTrack(
                    self.created, box, patch, timestamp, now,
                    first_yolo_at=detection.valid_yolo_at if detection.valid_yolo_at is not None else now,
                )
                self.active[track.id] = track
            track.record(box, patch, detection, timestamp, self.min_observations, now)
            seen.append(track)
        while len(self.active) > 32:
            oldest = min(self.active, key=lambda track_id: self.active[track_id].last_ms)
            self.unconfirmed_lost += not self.active.pop(oldest).offered
            self.lost += 1
        return seen
