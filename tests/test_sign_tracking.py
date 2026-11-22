import unittest

import numpy as np

from src.traffic_sign_demo.sign_tracking import SignTracker
from src.traffic_sign_demo.vision import ClassifiedDetection, DisplayFrame


class SignTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = SignTracker()
        self.patch = np.random.default_rng(42).integers(0, 255, (18, 24, 3), dtype=np.uint8)
        self.detection = ClassifiedDetection((20, 30, 44, 48), 4, "Give Way", 0.8, 13, "Yield", 0.94)

    def frame(
        self, index: int, x: int | None, session: int = 1
    ) -> DisplayFrame:
        pixels = np.zeros((90, 120, 3), dtype=np.uint8)
        if x is not None:
            pixels[30:48, x:x + 24] = self.patch
        return DisplayFrame(session, index, index * 50, 120, 90, pixels)

    def test_motion_uses_pixels_and_retains_the_original_classification(self) -> None:
        self.assertEqual(self.tracker.update(self.frame(0, 20), ()), ())
        self.tracker.update(self.frame(0, 20), (self.detection,))
        tracked, = self.tracker.update(self.frame(1, 27), ())
        self.assertEqual(tracked.bbox, (27, 30, 51, 48))
        self.assertEqual((tracked.cnn_class_name, tracked.cnn_score), ("Yield", 0.94))
        self.assertEqual(self.tracker.update(self.frame(2, None), ()), ())
        self.assertEqual(self.tracker.update(self.frame(3, 27), ()), ())

    def test_new_detection_reanchors_without_duplicate_overlay(self) -> None:
        self.tracker.update(self.frame(0, 20), (self.detection,))
        corrected = ClassifiedDetection((27, 30, 51, 48), 4, "Give Way", 0.9, 13, "Yield", 1)
        self.assertEqual(self.tracker.update(self.frame(1, 27), (corrected,)), (corrected,))

    def test_track_expires_and_never_crosses_playback_sessions(self) -> None:
        self.tracker.update(self.frame(0, 20), (self.detection,))
        for i in range(1, 8):
            self.assertTrue(self.tracker.update(self.frame(i, 20), ()))
        self.assertFalse(self.tracker.update(self.frame(8, 20), ()))
        self.tracker.update(self.frame(8, 20), (self.detection,))
        self.assertFalse(self.tracker.update(self.frame(9, 20, session=2), ()))
