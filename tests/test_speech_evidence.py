import unittest

import cv2
import numpy as np

from src.traffic_sign_demo.speech_evidence import speech_veto
from src.traffic_sign_demo.vision import preprocess_crop


class SpeechEvidenceTests(unittest.TestCase):
    def check(self, crop, class_id):
        return speech_veto(preprocess_crop(crop)[0], class_id)

    def test_dark_red_face_blocks_speed_and_other_predicted_classes(self):
        crop = np.full((40, 40, 3), (35, 35, 35), dtype=np.uint8)
        cv2.circle(crop, (20, 20), 14, (30, 25, 230), 4)
        cv2.line(crop, (18, 16), (18, 24), (230, 230, 230), 2)
        for label in (4, 7, 25, 34):
            with self.subTest(label=label):
                self.assertEqual(self.check(crop, label), "dark_red_sign_face")

    def test_light_face_is_required_for_speed_speech(self):
        crop = np.full((30, 30, 3), 40, dtype=np.uint8)
        self.assertEqual(self.check(crop, 4), "speed_face_unverified")
        crop[5:25, 5:25] = 225
        self.assertIsNone(self.check(crop, 4))

    def test_white_diamond_cannot_support_a_blue_mandatory_prediction(self):
        crop = np.full((30, 30, 3), 220, dtype=np.uint8)
        self.assertEqual(self.check(crop, 38), "mandatory_blue_face_unverified")
        self.assertIsNone(self.check(crop, 12))
        crop[5:25, 5:25] = (220, 90, 25)
        self.assertIsNone(self.check(crop, 38))

    def test_blue_cannot_enable_unvalidated_roundabout_speech(self):
        crop = np.full((30, 30, 3), (220, 90, 25), dtype=np.uint8)
        self.assertEqual(self.check(crop, 40), "roundabout_voice_unverified")
