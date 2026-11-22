from __future__ import annotations

from array import array
from collections import deque
from dataclasses import dataclass
import logging
import math
from pathlib import Path
import threading
import time
from typing import Callable
import wave

from .vietnamese_labels import VIETNAMESE_CLASSES
from .vision import ClassifiedDetection

logger = logging.getLogger(__name__)
_CLIPS = Path(__file__).resolve().parents[2] / "assets" / "voice_vi"
_GOOGLE_CLIPS = _CLIPS.with_name("voice_google")


@dataclass(frozen=True)
class ClipTiming:
    wav_seconds: float
    slot_seconds: float


def _play_clip(class_id: int) -> float:
    return _play_with_fallback(class_id, _play_wav)


def _play_spoken_clip(class_id: int) -> ClipTiming:
    return _play_with_fallback(
        class_id, lambda path: _start_wav(path, check_tail=path.parent == _GOOGLE_CLIPS)
    )


def _play_with_fallback(class_id, play):
    filename = f"{class_id:02}.wav"
    google = _GOOGLE_CLIPS / filename
    if google.is_file():
        try:
            return play(google)
        except (OSError, RuntimeError, wave.Error, EOFError):
            logger.warning("Google voice clip %s failed. Playing the eSpeak fallback.", filename)
    return play(_CLIPS / filename)


def _play_wav(path: Path) -> float:
    return _start_wav(path).wav_seconds


def _clip_timing(clip: wave.Wave_read, *, check_tail: bool) -> ClipTiming:
    frames, rate = clip.getnframes(), clip.getframerate()
    full = frames / rate
    if full <= 0:
        raise wave.Error("Empty voice clip")
    if not check_tail or clip.getnchannels() != 1 or clip.getsampwidth() != 2:
        return ClipTiming(full, full)
    # These Google clips have a low-level MP3 noise floor after speech.
    # Only release the slot after 170 ms below roughly -66 dBFS, and only
    # when an audible sample was found inside the inspected final second.
    tail_frames = min(rate, frames)
    clip.setpos(frames - tail_frames)
    samples = array("h", clip.readframes(tail_frames))
    if len(samples) != tail_frames:
        raise wave.Error("Truncated voice clip")
    quiet_frames = next((i for i, sample in enumerate(reversed(samples)) if abs(sample) >= 16), 0)
    releasable = max(0, quiet_frames / rate - 0.17)
    return ClipTiming(full, full - releasable)


def _start_wav(path: Path, *, check_tail: bool = False) -> ClipTiming:
    import winsound

    with wave.open(str(path), "rb") as clip:
        timing = _clip_timing(clip, check_tail=check_tail)
    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    return timing


def _stop_clip() -> None:
    import winsound

    winsound.PlaySound(None, 0)


@dataclass
class _RecentAlert:
    class_id: int
    bbox: tuple[float, float, float, float]
    time: float

    def matches(self, detection: ClassifiedDetection) -> bool:
        if self.class_id != detection.cnn_class_id:
            return False
        x, y, right, bottom = self.bbox
        nx, ny, nr, nb = detection.bbox
        distance = math.hypot((x + right - nx - nr) / 2, (y + bottom - ny - nb) / 2)
        radius = max(36, 1.2 * max(right - x, bottom - y, nr - nx, nb - ny))
        return distance <= radius


class VoiceAlerts:
    """Play fresh, local speech clips on a single background audio channel."""

    def __init__(
        self,
        play: Callable[[int], float] = _play_clip,
        stop: Callable[[], None] = _stop_clip,
    ) -> None:
        self._play = play
        self._stop = stop
        self._condition = threading.Condition()
        self._recent: deque[_RecentAlert] = deque(maxlen=32)
        self._pending: _RecentAlert | None = None
        self._generation = 0
        self._speaking = False
        self._closed = False
        self._failed = False
        self.status = "Voice ready"
        self._thread = threading.Thread(target=self._run, name="vietnamese-sign-alerts", daemon=True)
        self._thread.start()

    def offer(self, detections: tuple[ClassifiedDetection, ...]) -> None:
        now = time.monotonic()
        with self._condition:
            if self._closed or self._failed:
                return
            while self._recent and now - self._recent[0].time >= 4:
                self._recent.popleft()
            candidate = None
            for detection in detections:
                if detection.cnn_class_id not in VIETNAMESE_CLASSES:
                    continue
                match = next((alert for alert in self._recent if alert.matches(detection)), None)
                if match is not None:
                    match.bbox = detection.bbox
                elif candidate is None or detection.cnn_score > candidate.cnn_score:
                    candidate = detection
            if candidate is not None and not self._speaking and self._pending is None:
                alert = _RecentAlert(candidate.cnn_class_id, candidate.bbox, now)
                self._recent.append(alert)
                self._pending = alert
                self._condition.notify()

    def reset(self) -> None:
        with self._condition:
            self._generation += 1
            self._pending = None
            self._recent.clear()
            if not self._failed:
                self.status = "Voice ready"
            self._condition.notify()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._pending = None
            self._condition.notify()
        self._thread.join(timeout=0.25)

    def _run(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or self._pending is not None)
                if self._closed:
                    return
                alert = self._pending
                self._pending = None
                if time.monotonic() - alert.time > 0.5:
                    continue
                generation = self._generation
                self._speaking = True
            try:
                duration = self._play(alert.class_id)
                with self._condition:
                    if generation == self._generation and not self._closed:
                        self.status = f"Voice: {VIETNAMESE_CLASSES[alert.class_id]}"
                    interrupted = self._condition.wait_for(
                        lambda: self._closed or generation != self._generation, timeout=duration
                    )
                if interrupted:
                    self._stop()
            except Exception:
                logger.warning("Vietnamese voice playback failed.", exc_info=True)
                with self._condition:
                    self._failed = True
                    self.status = "Voice unavailable"
            finally:
                with self._condition:
                    self._speaking = False
