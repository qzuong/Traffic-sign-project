import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from src.traffic_sign_demo.video_reader import VideoReader, VideoReaderError


class FakeCapture:
    def __init__(
        self,
        opened: bool = True,
        fps: float = 24.0,
        frames: list[object] | None = None,
        frame_count: float | None = None,
        seek_supported: bool = True,
    ) -> None:
        self.opened = opened
        self.fps = fps
        self.frames = frames or []
        self.frame_count = float(len(self.frames)) if frame_count is None else frame_count
        self.seek_supported = seek_supported
        self.released = False
        self.position = 0

    def isOpened(self) -> bool:
        return self.opened

    def get(self, property_id: int) -> float:
        if property_id == cv2.CAP_PROP_FPS:
            return self.fps
        if property_id == cv2.CAP_PROP_FRAME_COUNT:
            return self.frame_count
        if property_id == cv2.CAP_PROP_POS_FRAMES:
            return float(self.position)
        raise AssertionError(f"Unexpected capture property: {property_id}")

    def read(self) -> tuple[bool, object | None]:
        if self.position >= len(self.frames):
            return False, None
        frame = self.frames[self.position]
        self.position += 1
        return True, frame

    def set(self, property_id: int, value: float) -> bool:
        if property_id != cv2.CAP_PROP_POS_FRAMES:
            raise AssertionError(f"Unexpected capture property: {property_id}")
        if not self.seek_supported:
            return False
        self.position = int(value)
        return True

    def release(self) -> None:
        self.released = True


class VideoReaderTests(unittest.TestCase):
    def test_open_reads_fps_and_frames_in_order(self) -> None:
        first = np.zeros((2, 2, 3), dtype=np.uint8)
        second = np.ones((2, 2, 3), dtype=np.uint8)
        capture = FakeCapture(frames=[first, second])
        reader = VideoReader(Path("sample.mp4"))

        with (
            patch.object(Path, "is_file", return_value=True),
            patch("src.traffic_sign_demo.video_reader.cv2.VideoCapture", return_value=capture),
        ):
            reader.open()
            self.assertEqual(reader.fps, 24.0)
            self.assertEqual(reader.frame_count, 2)
            self.assertAlmostEqual(reader.duration or 0, 2 / 24)
            self.assertIs(reader.read(), first)
            self.assertIs(reader.read(), second)
            self.assertIsNone(reader.read())
            reader.close()

        self.assertTrue(capture.released)

    def test_open_rejects_unreadable_capture(self) -> None:
        capture = FakeCapture(opened=False)
        reader = VideoReader("sample.avi")

        with (
            patch.object(Path, "is_file", return_value=True),
            patch("src.traffic_sign_demo.video_reader.cv2.VideoCapture", return_value=capture),
        ):
            with self.assertRaises(VideoReaderError):
                reader.open()

        self.assertTrue(capture.released)

    def test_seek_returns_reported_frame_position(self) -> None:
        frames = [np.full((2, 2, 3), index, dtype=np.uint8) for index in range(4)]
        capture = FakeCapture(frames=frames)
        reader = VideoReader("sample.mp4")

        with (
            patch.object(Path, "is_file", return_value=True),
            patch("src.traffic_sign_demo.video_reader.cv2.VideoCapture", return_value=capture),
        ):
            reader.open()
            frame, actual_index = reader.seek(2)
            reader.close()

        self.assertIs(frame, frames[2])
        self.assertEqual(actual_index, 2)
        self.assertTrue(capture.released)

    def test_seek_fails_if_capture_cannot_seek(self) -> None:
        capture = FakeCapture(frames=[np.zeros((2, 2, 3), dtype=np.uint8)], seek_supported=False)
        reader = VideoReader("sample.mp4")

        with (
            patch.object(Path, "is_file", return_value=True),
            patch("src.traffic_sign_demo.video_reader.cv2.VideoCapture", return_value=capture),
        ):
            reader.open()
            with self.assertRaises(VideoReaderError):
                reader.seek(0)
            reader.close()

    def test_missing_frame_count_disables_seeking(self) -> None:
        capture = FakeCapture(
            frames=[np.zeros((2, 2, 3), dtype=np.uint8)],
            frame_count=float("nan"),
        )
        reader = VideoReader("sample.mp4")

        with (
            patch.object(Path, "is_file", return_value=True),
            patch("src.traffic_sign_demo.video_reader.cv2.VideoCapture", return_value=capture),
        ):
            reader.open()
            self.assertIsNone(reader.frame_count)
            self.assertIsNone(reader.duration)
            with self.assertRaises(VideoReaderError):
                reader.seek(0)
            reader.close()

    def test_open_rejects_invalid_fps(self) -> None:
        capture = FakeCapture(fps=0.0)
        reader = VideoReader("sample.mp4")

        with (
            patch.object(Path, "is_file", return_value=True),
            patch("src.traffic_sign_demo.video_reader.cv2.VideoCapture", return_value=capture),
        ):
            with self.assertRaises(VideoReaderError):
                reader.open()

        self.assertTrue(capture.released)

    def test_open_rejects_unsupported_extension(self) -> None:
        reader = VideoReader("sample.mkv")

        with self.assertRaises(VideoReaderError):
            reader.open()

    def test_open_rejects_missing_file(self) -> None:
        reader = VideoReader("missing.mp4")

        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaises(VideoReaderError):
                reader.open()


if __name__ == "__main__":
    unittest.main()
