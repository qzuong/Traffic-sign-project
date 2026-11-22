from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


class VideoReaderError(Exception):
    """Raised when a video cannot be opened or decoded."""


class VideoReader:
    SUPPORTED_SUFFIXES = {".mp4", ".avi"}

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._capture: cv2.VideoCapture | None = None
        self._fps: float | None = None
        self._frame_count: int | None = None

    @property
    def fps(self) -> float:
        if self._fps is None:
            raise VideoReaderError("Video has not been opened.")
        return self._fps

    @property
    def frame_count(self) -> int | None:
        return self._frame_count

    @property
    def duration(self) -> float | None:
        if self._fps is None or self._frame_count is None:
            return None
        return self._frame_count / self._fps

    def open(self) -> None:
        if self._capture is not None:
            raise VideoReaderError("Video is already open.")
        if self.path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            raise VideoReaderError("Only MP4 and AVI video files are supported.")
        if not self.path.is_file():
            raise VideoReaderError(f"File does not exist: {self.path}")

        capture: cv2.VideoCapture | None = None
        try:
            if hasattr(cv2, "CAP_PROP_N_THREADS"):
                capture = cv2.VideoCapture(
                    str(self.path), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 2]
                )
            if capture is None or not capture.isOpened():
                if capture is not None:
                    capture.release()
                capture = cv2.VideoCapture(str(self.path))
            if not capture.isOpened():
                capture.release()
                raise VideoReaderError(f"Could not open video file: {self.path}")

            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if not math.isfinite(fps) or fps <= 0:
                capture.release()
                raise VideoReaderError(
                    f"Could not read a valid frame rate from: {self.path}"
                )

            raw_frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            rounded_frame_count = (
                round(raw_frame_count) if math.isfinite(raw_frame_count) else 0
            )
            frame_count = (
                int(rounded_frame_count) if rounded_frame_count > 0 else None
            )
        except cv2.error as exc:
            if capture is not None:
                capture.release()
            raise VideoReaderError(f"Could not open video file: {self.path}") from exc

        self._capture = capture
        self._fps = fps
        self._frame_count = frame_count

    def read(self) -> np.ndarray | None:
        if self._capture is None:
            raise VideoReaderError("Video is not open.")

        try:
            success, frame = self._capture.read()
        except cv2.error as exc:
            raise VideoReaderError(f"Could not decode video file: {self.path}") from exc

        if not success:
            return None
        if frame is None or frame.size == 0:
            raise VideoReaderError(f"Video contains an empty frame: {self.path}")
        return frame

    def seek(self, frame_index: int) -> tuple[np.ndarray, int]:
        if self._capture is None:
            raise VideoReaderError("Video is not open.")
        if self._frame_count is None:
            raise VideoReaderError("The video frame count is unavailable; seeking is disabled.")
        if not 0 <= frame_index < self._frame_count:
            raise VideoReaderError(
                f"Frame index must be between 0 and {self._frame_count - 1}."
            )

        try:
            if not self._capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
                raise VideoReaderError(f"Could not seek to frame {frame_index}.")

            success, frame = self._capture.read()
            if not success or frame is None or frame.size == 0:
                raise VideoReaderError(f"Could not read a frame after seeking to {frame_index}.")

            position = float(self._capture.get(cv2.CAP_PROP_POS_FRAMES))
            if not math.isfinite(position) or position < 1:
                raise VideoReaderError("Could not verify the actual frame position after seeking.")

            actual_index = round(position) - 1
            if actual_index >= self._frame_count:
                actual_index = self._frame_count - 1
            return frame, actual_index
        except cv2.error as exc:
            raise VideoReaderError(f"Could not seek in video file: {self.path}") from exc

    def skip(self) -> bool:
        if self._capture is None:
            raise VideoReaderError("Video is not open.")
        try:
            return self._capture.grab()
        except cv2.error as exc:
            raise VideoReaderError(f"Could not advance in video file: {self.path}") from exc

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._fps = None
        self._frame_count = None
