from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from .video_reader import VideoReader, VideoReaderError


class PlaybackState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"


class PlaybackStateError(Exception):
    """Raised when a playback command is invalid for the current state."""


class PlaybackEventType(Enum):
    OPEN_NEW_VIDEO = "open_new_video"
    REPLAY = "replay"
    SEEK = "seek"
    STOP = "stop"


@dataclass(frozen=True)
class PlaybackEvent:
    event_type: PlaybackEventType
    path: Path
    frame_index: int


PlaybackEventListener = Callable[[PlaybackEvent], None]


class VideoReaderPort(Protocol):
    @property
    def fps(self) -> float: ...

    @property
    def frame_count(self) -> int | None: ...

    @property
    def duration(self) -> float | None: ...

    def open(self) -> None: ...

    def read(self) -> np.ndarray | None: ...

    def seek(self, frame_index: int) -> tuple[np.ndarray, int]: ...

    def close(self) -> None: ...


ReaderFactory = Callable[[Path], VideoReaderPort]


class PlaybackController:
    MAX_SKIPPED_FRAMES_PER_TICK = 8

    def __init__(self, reader_factory: ReaderFactory = VideoReader) -> None:
        self._reader_factory = reader_factory
        self._reader: VideoReaderPort | None = None
        self._state = PlaybackState.STOPPED
        self._frame_index = 0
        self._path: Path | None = None
        self._fps: float | None = None
        self._frame_count: int | None = None
        self._duration: float | None = None
        self._event_listeners: list[PlaybackEventListener] = []

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def fps(self) -> float:
        if self._fps is None:
            raise PlaybackStateError("There is no valid video frame rate.")
        return self._fps

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def frame_count(self) -> int | None:
        return self._frame_count

    @property
    def duration(self) -> float | None:
        return self._duration

    def add_event_listener(self, listener: PlaybackEventListener) -> None:
        self._event_listeners.append(listener)

    def start(self, path: str | Path) -> np.ndarray:
        self._release_reader()
        self._reset_video_metadata()
        self._path = None
        self._frame_index = 0
        self._state = PlaybackState.STOPPED

        selected_path = Path(path)
        first_frame = self._open_reader(selected_path)
        self._path = selected_path
        self._frame_index = 1
        self._state = PlaybackState.PLAYING
        self._emit_event(PlaybackEventType.OPEN_NEW_VIDEO)
        return first_frame

    def replay(self) -> np.ndarray:
        if self._path is None:
            raise PlaybackStateError("There is no video available to replay.")

        path = self._path
        self._release_reader()
        self._frame_index = 0
        self._state = PlaybackState.STOPPED
        first_frame = self._open_reader(path)
        self._frame_index = 1
        self._state = PlaybackState.PLAYING
        self._emit_event(PlaybackEventType.REPLAY)
        return first_frame

    def read_next(self, target_index: int | None = None) -> np.ndarray | None:
        if self._state is not PlaybackState.PLAYING or self._reader is None:
            raise PlaybackStateError("Video can only advance while playing.")

        if target_index is not None and self._frame_count is not None:
            target_index = min(target_index, self._frame_count - 1)
        if target_index is not None:
            target_index = min(target_index, self._frame_index + self.MAX_SKIPPED_FRAMES_PER_TICK)
        skip = getattr(self._reader, "skip", None)
        while target_index is not None and self._frame_index < target_index:
            if not (skip() if skip is not None else self._reader.read() is not None):
                break
            self._frame_index += 1
        frame = self._reader.read()
        if frame is None:
            self._release_reader()
            self._state = PlaybackState.COMPLETED
            return None

        self._frame_index += 1
        return frame

    def pause(self) -> None:
        if self._state is not PlaybackState.PLAYING:
            raise PlaybackStateError("Only a playing video can be paused.")
        self._state = PlaybackState.PAUSED

    def resume(self) -> None:
        if self._state is not PlaybackState.PAUSED:
            raise PlaybackStateError("Only a paused video can be resumed.")
        self._state = PlaybackState.PLAYING

    def seek(self, frame_index: int) -> np.ndarray:
        if self._state not in {
            PlaybackState.PLAYING,
            PlaybackState.PAUSED,
            PlaybackState.COMPLETED,
        }:
            raise PlaybackStateError("There is no active video session to seek.")
        if self._path is None or self._frame_count is None:
            raise PlaybackStateError("Seeking is unavailable for this video.")
        if not 0 <= frame_index < self._frame_count:
            raise PlaybackStateError(
                f"Frame index must be between 0 and {self._frame_count - 1}."
            )

        previous_state = self._state
        opened_for_seek = self._reader is None
        if opened_for_seek:
            self._reader = self._reader_factory(self._path)
            try:
                self._reader.open()
                self._update_metadata(self._reader)
            except VideoReaderError:
                self._release_reader()
                raise

        if self._reader is None:
            raise PlaybackStateError("There is no open video reader.")

        try:
            frame, actual_index = self._reader.seek(frame_index)
        except VideoReaderError:
            if opened_for_seek:
                self._release_reader()
            raise

        self._frame_index = actual_index + 1
        if previous_state is PlaybackState.COMPLETED:
            self._state = PlaybackState.PAUSED
        self._emit_event(PlaybackEventType.SEEK)
        return frame

    def stop(self) -> None:
        had_session = self._path is not None and self._state is not PlaybackState.STOPPED
        self._release_reader()
        self._frame_index = 0
        self._state = PlaybackState.STOPPED
        if had_session:
            self._emit_event(PlaybackEventType.STOP)

    def _open_reader(self, path: Path) -> np.ndarray:
        reader = self._reader_factory(path)
        try:
            reader.open()
            self._update_metadata(reader)
            first_frame = reader.read()
            if first_frame is None:
                raise VideoReaderError(f"No readable video frames found: {path}")
        except VideoReaderError:
            reader.close()
            raise

        self._reader = reader
        return first_frame

    def _update_metadata(self, reader: VideoReaderPort) -> None:
        self._fps = reader.fps
        self._frame_count = reader.frame_count
        self._duration = reader.duration

    def _reset_video_metadata(self) -> None:
        self._fps = None
        self._frame_count = None
        self._duration = None

    def _release_reader(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None

    def _emit_event(self, event_type: PlaybackEventType) -> None:
        if self._path is None:
            return
        event = PlaybackEvent(event_type, self._path, self._frame_index)
        for listener in tuple(self._event_listeners):
            listener(event)
