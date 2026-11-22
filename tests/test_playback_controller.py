import unittest
from pathlib import Path

import numpy as np

from src.traffic_sign_demo.playback_controller import (
    PlaybackEvent,
    PlaybackEventType,
    PlaybackController,
    PlaybackState,
    PlaybackStateError,
)
from src.traffic_sign_demo.video_reader import VideoReaderError


class FakeReader:
    def __init__(self, frames: list[np.ndarray], fps: float = 25.0) -> None:
        self.frames = frames
        self.fps = fps
        self.closed = False
        self.position = 0

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def duration(self) -> float:
        return self.frame_count / self.fps

    def open(self) -> None:
        self.closed = False
        self.position = 0

    def read(self) -> np.ndarray | None:
        if self.position >= len(self.frames):
            return None
        frame = self.frames[self.position]
        self.position += 1
        return frame

    def seek(self, frame_index: int) -> tuple[np.ndarray, int]:
        self.position = frame_index
        frame = self.read()
        if frame is None:
            raise VideoReaderError("No frame at requested index.")
        return frame, frame_index

    def close(self) -> None:
        self.closed = True


class PlaybackControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.first = np.zeros((2, 2, 3), dtype=np.uint8)
        self.second = np.ones((2, 2, 3), dtype=np.uint8)
        self.third = np.full((2, 2, 3), 2, dtype=np.uint8)
        self.readers: list[FakeReader] = []
        self.reader_paths: list[Path] = []
        self.events: list[PlaybackEvent] = []

        def create_reader(path: Path) -> FakeReader:
            self.reader_paths.append(path)
            reader = FakeReader([self.first, self.second, self.third])
            self.readers.append(reader)
            return reader

        self.controller = PlaybackController(create_reader)
        self.controller.add_event_listener(self.events.append)

    def test_start_pause_resume_preserves_frame_order(self) -> None:
        first = self.controller.start(Path("sample.mp4"))
        self.assertIs(first, self.first)
        self.assertEqual(self.controller.state, PlaybackState.PLAYING)
        self.assertEqual(self.controller.frame_index, 1)

        self.controller.pause()
        self.assertEqual(self.controller.state, PlaybackState.PAUSED)
        with self.assertRaises(PlaybackStateError):
            self.controller.read_next()

        self.controller.resume()
        second = self.controller.read_next()
        self.assertIs(second, self.second)
        self.assertEqual(self.controller.frame_index, 2)

    def test_end_of_video_marks_session_completed(self) -> None:
        self.controller.start("sample.mp4")
        self.controller.read_next()
        self.controller.read_next()

        self.assertIsNone(self.controller.read_next())
        self.assertEqual(self.controller.state, PlaybackState.COMPLETED)
        self.assertTrue(self.readers[0].closed)

    def test_clock_catchup_preserves_exact_frame_index(self) -> None:
        self.controller.start("sample.mp4")
        self.assertIs(self.controller.read_next(target_index=2), self.third)
        self.assertEqual(self.controller.frame_index - 1, 2)
        self.assertIsNone(self.controller.read_next(target_index=100))

    def test_stop_releases_reader_and_resets_session(self) -> None:
        self.controller.start("sample.mp4")
        self.controller.stop()

        self.assertTrue(self.readers[0].closed)
        self.assertEqual(self.controller.state, PlaybackState.STOPPED)
        self.assertEqual(self.controller.frame_index, 0)

    def test_start_rejects_video_without_readable_frames(self) -> None:
        reader = FakeReader([])
        controller = PlaybackController(lambda _path: reader)

        with self.assertRaises(VideoReaderError):
            controller.start("empty.mp4")

        self.assertTrue(reader.closed)
        self.assertEqual(controller.state, PlaybackState.STOPPED)

    def test_replay_after_completion_reopens_first_frame(self) -> None:
        self.controller.start("sample.mp4")
        self.controller.read_next()
        self.controller.read_next()
        self.assertIsNone(self.controller.read_next())

        replay_frame = self.controller.replay()

        self.assertIs(replay_frame, self.first)
        self.assertEqual(self.controller.state, PlaybackState.PLAYING)
        self.assertEqual(self.controller.frame_index, 1)
        self.assertEqual(
            [event.event_type for event in self.events],
            [PlaybackEventType.OPEN_NEW_VIDEO, PlaybackEventType.REPLAY],
        )

    def test_replay_after_stop_reopens_first_frame(self) -> None:
        self.controller.start("sample.mp4")
        self.controller.stop()

        self.assertIs(self.controller.replay(), self.first)
        self.assertEqual(self.controller.state, PlaybackState.PLAYING)
        self.assertEqual(self.events[-2].event_type, PlaybackEventType.STOP)
        self.assertEqual(self.events[-1].event_type, PlaybackEventType.REPLAY)

    def test_seek_preserves_playing_and_paused_states(self) -> None:
        self.controller.start("sample.mp4")

        self.assertIs(self.controller.seek(1), self.second)
        self.assertEqual(self.controller.state, PlaybackState.PLAYING)
        self.assertEqual(self.controller.frame_index, 2)

        self.controller.pause()
        self.assertIs(self.controller.seek(2), self.third)
        self.assertEqual(self.controller.state, PlaybackState.PAUSED)
        self.assertEqual(self.controller.frame_index, 3)
        self.assertEqual(self.events[-1].event_type, PlaybackEventType.SEEK)

    def test_seek_after_completion_moves_to_paused_state(self) -> None:
        self.controller.start("sample.mp4")
        self.controller.read_next()
        self.controller.read_next()
        self.controller.read_next()

        self.assertEqual(self.controller.state, PlaybackState.COMPLETED)
        self.assertIs(self.controller.seek(0), self.first)
        self.assertEqual(self.controller.state, PlaybackState.PAUSED)
        self.assertEqual(self.controller.frame_index, 1)

        self.controller.resume()
        self.assertIs(self.controller.read_next(), self.second)

    def test_replay_and_seek_fail_without_a_valid_video(self) -> None:
        with self.assertRaises(PlaybackStateError):
            self.controller.replay()
        with self.assertRaises(PlaybackStateError):
            self.controller.seek(0)

    def test_open_new_video_after_replay_and_seek_resets_reader(self) -> None:
        self.controller.start("first.mp4")
        self.controller.seek(2)
        self.controller.replay()
        previous_reader = self.readers[-1]

        self.controller.start("second.mp4")

        self.assertTrue(previous_reader.closed)
        self.assertEqual(self.controller.path, Path("second.mp4"))
        self.assertEqual(self.controller.state, PlaybackState.PLAYING)
        self.assertEqual(self.controller.frame_index, 1)
        self.assertEqual(self.reader_paths[-1], Path("second.mp4"))
        self.assertEqual(self.events[-1].event_type, PlaybackEventType.OPEN_NEW_VIDEO)


if __name__ == "__main__":
    unittest.main()
