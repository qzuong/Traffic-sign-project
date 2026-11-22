from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import logging
import threading
import time

from .alert_tracking import AlertTrack, AlertTracks
from .vietnamese_labels import VIETNAMESE_CLASSES
from .vision import ClassifiedDetection, DisplayFrame
from .voice_alerts import ClipTiming, _play_spoken_clip, _stop_clip

logger = logging.getLogger(__name__)
# Yield, stop, wrong-way, and selected immediate roadway hazards precede
# routine signs. A current alert waiting 2.2 s takes precedence at the
# next free audio slot. Each tier serves the earliest confirmation first.
_URGENT = {13, 14, 17, 19, 20, 23, 25, 26, 27, 28}
_TRACK_FRESH_MS = 700
_FRAME_STALL_SECONDS = 0.75
_PRIORITY_AGE_SECONDS = 2.2


@dataclass(frozen=True)
class _Pending:
    class_id: int
    created_at: float
    first_yolo_at: float


class TrackedVoiceAlerts:
    """Confirm sign observations and schedule one current Vietnamese clip at a time."""

    def __init__(self, min_observations=2, capacity=3, play=_play_spoken_clip, stop=_stop_clip,
                 *, clock=time.monotonic, on_confirmation=None) -> None:
        if capacity < 1:
            raise ValueError("Voice queue capacity must be positive.")
        self._tracker = AlertTracks(min_observations)
        self._capacity = capacity
        self._play, self._stop = play, stop
        self._clock = clock
        self._on_confirmation = on_confirmation
        self._condition = threading.Condition()
        self._pending: dict[int, _Pending] = {}
        self._generation = 0
        self._media_ms = -1.0
        self._image_size = (0, 0)
        self._last_frame_at = 0.0
        self._closed = False
        self._completed = False
        self._failed = False
        self._speaking = False
        self._active_cancel: tuple[str, float] | None = None
        self._counts = Counter()
        self._confirmed_classes: set[int] = set()
        self._measurements: deque[dict] = deque(maxlen=200)
        self._events: deque[dict] = deque(maxlen=2048)
        self._played_ids: deque[tuple[int, int]] = deque(maxlen=200)
        self.status = "Voice ready"
        self._thread = threading.Thread(
            target=self._run, name="tracked-vietnamese-sign-alerts", daemon=True
        )
        self._thread.start()

    @property
    def diagnostics(self) -> dict:
        with self._condition:
            return {
                **dict.fromkeys(("generated", "accepted", "played", "expired", "duplicates_suppressed"), 0),
                **dict(self._counts), "tracks_created": self._tracker.created,
                "tracks_lost": self._tracker.lost, "ambiguous_associations": self._tracker.ambiguous,
                "unresolved_associations": self._tracker.unresolved_associations,
                "unconfirmed_tracks_lost": self._tracker.unconfirmed_lost,
                "confirmed_classes": sorted(self._confirmed_classes),
                "pending": len(self._pending),
                "speech_latency_ms": tuple(row["detection_to_speech_ms"] for row in self._measurements),
                "measurements": tuple(self._measurements),
                "played_tracks": tuple(self._played_ids),
            }

    @property
    def trace(self) -> tuple[dict, ...]:
        with self._condition:
            return tuple(self._events)

    def _event(self, name, now, track_id, *, generation=None, **details):
        self._events.append({
            "event": name, "monotonic": now, "video_ms": self._media_ms,
            "generation": self._generation if generation is None else generation,
            "track_id": track_id, **details,
        })
        if name in {
            "confirmed",
            "accepted",
            "expired",
            "audio_started",
            "audio_finished",
            "audio_cancelled",
            "audio_error",
            "speech_suppressed",
        }:
            logger.debug(
                "Voice/tracking event=%s track_id=%s details=%s.",
                name,
                track_id,
                details,
            )

    def observe(
        self, frame: DisplayFrame, detections: tuple[ClassifiedDetection, ...]
    ) -> list[tuple[int, tuple[int, int, int, int], int | None]]:
        now = self._clock()
        with self._condition:
            if (self._closed or self._completed or frame.timestamp_ms < self._media_ms
                    or (self._failed and self._on_confirmation is None)):
                return []
            self._media_ms, self._last_frame_at = frame.timestamp_ms, now
            height, width = frame.image.shape[:2]
            self._image_size = (width, height)
            created = self._tracker.created
            unresolved = self._tracker.unresolved_associations
            classified = {
                track.id for track in self._tracker.active.values() if track.first_cnn_at is not None
            } if detections else set()
            seen = self._tracker.update(frame, detections, now)
            now = self._clock()
            rejected = self._tracker.unresolved_associations - unresolved
            if rejected:
                self._event("association_rejected", now, None, count=rejected)
            self._expire(now)
            for track in seen:
                if track.id > created:
                    self._event("yolo_valid", track.first_yolo_at, track.id, frame_id=frame.frame_id)
                    self._event("track_created", track.first_seen, track.id, frame_id=frame.frame_id)
                if track.id not in classified and track.first_cnn_at is not None:
                    self._event("cnn_valid", track.first_cnn_at, track.id, frame_id=frame.frame_id)
                if track.confirmed is None or track.id not in self._tracker.active:
                    continue
                if self._on_confirmation is not None:
                    self._on_confirmation(frame, track)
                if self._failed:
                    continue
                self._confirmed_classes.add(track.confirmed)
                if track.speech_block is not None:
                    key = track.confirmed, track.speech_block
                    if key not in track.speech_suppressions:
                        if not track.speech_suppressions:
                            self._counts["tracks_with_speech_suppression"] += 1
                        track.speech_suppressions.add(key)
                        self._counts[f"speech_suppressed_{track.speech_block}"] += 1
                        self._event("speech_suppressed", now, track.id, frame_id=frame.frame_id,
                                    class_id=track.confirmed, reason=track.speech_block)
                    continue
                if track.offered:
                    self._counts["duplicates_suppressed"] += 1
                    continue
                track.offered = True
                self._counts["generated"] += 1
                self._event("confirmed", now, track.id, class_id=track.confirmed,
                            detection_to_confirmation_ms=(now - track.first_yolo_at) * 1000)
                self._event("offered", now, track.id, class_id=track.confirmed, busy=self._speaking)
                if self._speaking:
                    self._counts["queued_while_speaking"] += 1
                self._pending[track.id] = _Pending(track.confirmed, now, track.first_yolo_at)
                if len(self._pending) > self._capacity:
                    evicted = min(self._pending, key=lambda track_id: self._priority(track_id, now))
                    del self._pending[evicted]
                    self._counts["overflow"] += 1
                    self._event("rejected" if evicted == track.id else "evicted", now, evicted,
                                reason="queue_full")
                if track.id in self._pending:
                    self._counts["accepted"] += 1
                    self._event("accepted", now, track.id)
            self._counts["peak_queue"] = max(self._counts["peak_queue"], len(self._pending))
            if self._pending:
                self._condition.notify()
            return [(track.id, track.box, track.confirmed) for track in seen]

    def _priority(self, track_id: int, now: float) -> tuple[bool, bool, bool, float, int]:
        alert = self._pending[track_id]
        aged = now - alert.created_at >= _PRIORITY_AGE_SECONDS
        return (
            self._tracker.active[track_id].speech_class == alert.class_id,
            aged,
            not aged and alert.class_id in _URGENT,
            -alert.created_at, -track_id,
        )

    def _expiration_reason(self, track: AlertTrack | None, alert: _Pending, now: float) -> str | None:
        if track is None:
            return "sign_stale"
        if track.confirmed is not None and track.confirmed != alert.class_id:
            return "label_changed"
        gap = self._media_ms - track.last_ms
        if gap > _TRACK_FRESH_MS:
            return "tracking_uncertain" if track.confirmed is None else "sign_stale"
        if gap > 0 and self._leaving_view(track, gap):
            return "sign_left_view"
        if now - self._last_frame_at >= _FRAME_STALL_SECONDS:
            return "video_stalled"
        return None

    def _leaving_view(self, track: AlertTrack, gap: float) -> bool:
        # Trust an exit prediction only for a sign last seen near that edge.
        width, height = self._image_size
        left, top, right, bottom = track.box
        dx, dy = (velocity * gap for velocity in track.velocity)
        return (
            (right >= 0.9 * width and left + dx >= width)
            or (left <= 0.1 * width and right + dx <= 0)
            or (bottom >= 0.9 * height and top + dy >= height)
            or (top <= 0.1 * height and bottom + dy <= 0)
        )

    def _expire(self, now: float) -> None:
        for track_id, alert in tuple(self._pending.items()):
            reason = self._expiration_reason(self._tracker.active.get(track_id), alert, now)
            if reason:
                del self._pending[track_id]
                self._counts["expired"] += 1
                self._counts[f"expired_{reason}"] += 1
                self._event("expired", now, track_id, class_id=alert.class_id, reason=reason,
                            busy=self._speaking, queue_ms=(now - alert.created_at) * 1000)

    def suspend(self) -> None:
        with self._condition:
            self._cancel()

    def complete(self) -> None:
        """Discard pending alerts at end of video; finish any audio already started."""
        with self._condition:
            self._completed = True
            self._cancel_pending("end_of_video")
            self._condition.notify()

    def reset(self, reason: str = "reset") -> None:
        with self._condition:
            self._cancel(reason)
            self._completed = False
            self._tracker = AlertTracks(self._tracker.min_observations)
            self._media_ms = -1.0
            self._last_frame_at = 0.0
            self._counts.clear()
            self._confirmed_classes.clear()
            self._measurements.clear()
            self._played_ids.clear()

    def _cancel(self, reason: str = "pause") -> None:
        self._cancel_pending(reason)
        self._generation += 1
        if self._speaking and self._active_cancel is None:
            self._active_cancel = reason, self._media_ms
        if not self._failed:
            self.status = "Voice ready"
        self._condition.notify()

    def _cancel_pending(self, reason):
        self._counts["cancelled"] += len(self._pending)
        now = self._clock()
        for track_id in self._pending:
            self._event("cancelled", now, track_id, reason=reason)
        self._pending.clear()

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._cancel("close")
        self._thread.join(timeout=0.25)

    def _run(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or bool(self._pending))
                if self._closed:
                    return
                now = self._clock()
                self._expire(now)
                if not self._pending:
                    continue
                track_id = max(self._pending, key=lambda track_id: self._priority(track_id, now))
                if self._tracker.active[track_id].speech_class != self._pending[track_id].class_id:
                    # Wait for fresh confirmation or retire the queue on a stalled video.
                    self._condition.wait(timeout=max(0, self._last_frame_at + _FRAME_STALL_SECONDS - now))
                    continue
                alert = self._pending.pop(track_id)
                generation = self._generation
                last_seen_ms = self._tracker.active[track_id].last_ms
                dispatch_video_ms = self._media_ms
                self._speaking = True
                self._active_cancel = None
            try:
                timing = self._play(alert.class_id)
                if not isinstance(timing, ClipTiming):
                    timing = ClipTiming(timing, timing)
                with self._condition:
                    started = self._clock()
                    measurement = {
                        "track_id": track_id, "class_id": alert.class_id,
                        "detection_to_confirmation_ms": (alert.created_at - alert.first_yolo_at) * 1000,
                        "detection_to_speech_ms": (started - alert.first_yolo_at) * 1000,
                        "confirmation_to_speech_ms": (started - alert.created_at) * 1000,
                        "queue_ms": (now - alert.created_at) * 1000,
                        "wav_ms": timing.wav_seconds * 1000, "slot_ms": timing.slot_seconds * 1000,
                        "dispatch_video_ms": dispatch_video_ms, "last_seen_video_ms": last_seen_ms,
                    }
                    self._event("audio_started", started, track_id, generation=generation,
                                video_ms=dispatch_video_ms,
                                **{k: v for k, v in measurement.items() if k != "track_id"})
                    if generation == self._generation and not self._closed:
                        self._counts["played"] += 1
                        self._measurements.append(measurement)
                        self._played_ids.append((track_id, alert.class_id))
                        self.status = f"Voice confirmed: {VIETNAMESE_CLASSES[alert.class_id]}"
                    interrupted = self._condition.wait_for(
                        lambda: self._closed or generation != self._generation,
                        timeout=max(0, started + timing.slot_seconds - self._clock()),
                    )
                if interrupted or timing.slot_seconds < timing.wav_seconds:
                    self._stop()
                with self._condition:
                    reason, video_ms = self._active_cancel or (None, self._media_ms)
                    self._event("audio_cancelled" if interrupted else "audio_finished",
                                self._clock(), track_id, generation=generation,
                                class_id=alert.class_id, reason=reason, video_ms=video_ms)
            except Exception:
                logger.warning("Vietnamese voice playback failed.", exc_info=True)
                with self._condition:
                    self._failed = True
                    self._event("audio_error", self._clock(), track_id, generation=generation)
                    self._cancel_pending("worker_error")
                    self.status = "Voice unavailable"
            finally:
                with self._condition:
                    self._speaking = False
