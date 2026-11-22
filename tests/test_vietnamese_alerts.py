from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, call, patch
import wave

import numpy as np

from src.traffic_sign_demo.vietnamese_labels import VIETNAMESE_CLASSES, alert_sentence
from src.traffic_sign_demo.vision import ClassifiedDetection, draw_overlay
from src.traffic_sign_demo import voice_alerts
from src.traffic_sign_demo.voice_alerts import VoiceAlerts


_YIELD = ClassifiedDetection((20, 30, 40, 50), 0, "traffic_sign", 0.7, 13, "Yield", 0.9)
_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "voice_vi"
_GOOGLE = _ASSETS.with_name("voice_google")


class VietnamesePresentationTests(unittest.TestCase):
    def test_labels_and_spoken_examples(self) -> None:
        self.assertEqual(set(VIETNAMESE_CLASSES), set(range(43)))
        self.assertEqual(VIETNAMESE_CLASSES[13], "Nhường đường")
        self.assertEqual(VIETNAMESE_CLASSES[16], "Cấm xe tải (trên 3.5 tấn)")
        examples = {
            7: "Phía trước có biển báo tốc độ tối đa 100 ki lô mét trên giờ.",
            13: "Phía trước có biển nhường đường.",
            14: "Phía trước có biển dừng lại.",
            17: "Phía trước có biển cấm đi ngược chiều.",
            28: "Phía trước có biển báo trẻ em qua đường.",
            33: "Phía trước có biển hiệu lệnh rẽ phải.",
        }
        for class_id, sentence in examples.items():
            self.assertEqual(alert_sentence(VIETNAMESE_CLASSES[class_id]), sentence)

    def test_all_bundled_clips_match_the_alert_sentences(self) -> None:
        manifest = json.loads((_ASSETS / "provenance.json").read_text(encoding="utf-8"))["clips"]
        for class_id, label in VIETNAMESE_CLASSES.items():
            with self.subTest(class_id=class_id), wave.open(str(_ASSETS / f"{class_id:02}.wav")) as clip:
                self.assertEqual(manifest[str(class_id)]["text"], alert_sentence(label))
                self.assertGreater(clip.getnframes() / clip.getframerate(), 0.5)

    def test_google_assets_cover_all_classes_and_keep_approved_previews(self) -> None:
        manifest = json.loads((_GOOGLE / "provenance.json").read_text(encoding="utf-8"))
        previews = json.loads(
            (_ASSETS.with_name("voice_google_samples") / "samples.json").read_text(encoding="utf-8")
        )["samples"]
        self.assertEqual(manifest["generator"], "gTTS 2.5.4")
        self.assertEqual(manifest["lang"], "vi")
        self.assertEqual(set(manifest["clips"]), set(map(str, VIETNAMESE_CLASSES)))
        for class_id, label in VIETNAMESE_CLASSES.items():
            with self.subTest(class_id=class_id):
                entry = manifest["clips"][str(class_id)]
                self.assertEqual(entry["text"], alert_sentence(label))
                for fmt in ("mp3", "wav"):
                    path = _GOOGLE / f"{class_id:02}.{fmt}"
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry[f"{fmt}_sha256"])
                with wave.open(str(_GOOGLE / f"{class_id:02}.wav"), "rb") as clip:
                    self.assertEqual(clip.getsampwidth(), 2)
                    self.assertGreater(clip.getnframes(), 0)
        for sample in previews:
            entry = manifest["clips"][str(sample["class_id"])]
            self.assertEqual(entry["mp3_sha256"], sample["sha256"])

    def test_label_near_edge_has_white_text_and_dark_background(self) -> None:
        base = np.full((360, 640, 3), 150, dtype=np.uint8)
        detection = replace(_YIELD, bbox=(580, 15, 630, 55))
        overlay = draw_overlay(base, (detection,), 640, 360)
        np.testing.assert_array_equal(overlay[15, 580], (40, 220, 40))
        label_area = overlay[60:100, 440:640, 0]
        self.assertTrue(np.any(label_area == 20))
        self.assertTrue(np.any(label_area == 255))
        self.assertTrue(np.all(base == 150))


class VoiceAlertTests(unittest.TestCase):
    def test_espeak_fallback_keeps_the_full_playback_slot(self) -> None:
        with (
            patch.object(voice_alerts, "_GOOGLE_CLIPS", _GOOGLE / "missing-directory"),
            patch.object(voice_alerts, "_start_wav", return_value=voice_alerts.ClipTiming(1.8, 1.8)) as play,
        ):
            self.assertEqual(voice_alerts._play_spoken_clip(13), voice_alerts.ClipTiming(1.8, 1.8))
            play.assert_called_once_with(_ASSETS / "13.wav", check_tail=False)

    def test_google_slot_keeps_every_sample_above_the_quiet_threshold(self) -> None:
        for path in sorted(_GOOGLE.glob("*.wav")):
            with self.subTest(path=path), wave.open(str(path), "rb") as clip:
                timing = voice_alerts._clip_timing(clip, check_tail=True)
                self.assertLess(timing.slot_seconds, timing.wav_seconds)
                self.assertGreaterEqual(timing.slot_seconds, timing.wav_seconds - 0.83)
                cutoff = round(timing.slot_seconds * clip.getframerate())
                clip.setpos(cutoff)
                tail = np.frombuffer(clip.readframes(clip.getnframes() - cutoff), dtype="<i2")
                self.assertLess(np.max(np.abs(tail)), 16)
            with wave.open(str(path), "rb") as clip:
                timing = voice_alerts._clip_timing(clip, check_tail=False)
                self.assertEqual(timing.slot_seconds, timing.wav_seconds)

    def test_google_clip_is_preferred(self) -> None:
        with patch.object(voice_alerts, "_play_wav", return_value=2.4) as play:
            self.assertEqual(voice_alerts._play_clip(13), 2.4)
            play.assert_called_once_with(_GOOGLE / "13.wav")

    def test_missing_google_clip_uses_espeak(self) -> None:
        with (
            patch.object(voice_alerts, "_GOOGLE_CLIPS", _GOOGLE / "missing-directory"),
            patch.object(voice_alerts, "_play_wav", return_value=1.8) as play,
        ):
            self.assertEqual(voice_alerts._play_clip(13), 1.8)
            play.assert_called_once_with(_ASSETS / "13.wav")

    def test_invalid_google_clip_uses_espeak(self) -> None:
        with (
            patch.object(voice_alerts, "_play_wav", side_effect=[wave.Error("bad clip"), 1.8]) as play,
            self.assertLogs("src.traffic_sign_demo.voice_alerts", level="WARNING"),
        ):
            self.assertEqual(voice_alerts._play_clip(13), 1.8)
            self.assertEqual(play.call_args_list, [call(_GOOGLE / "13.wav"), call(_ASSETS / "13.wav")])

    def wait_until(self, predicate) -> None:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Voice worker did not reach the expected state.")

    def test_repeated_nearby_signs_are_suppressed_and_a_distant_sign_can_speak(self) -> None:
        play = Mock(return_value=0.01)
        alerts = VoiceAlerts(play=play, stop=Mock())
        self.addCleanup(alerts.close)
        alerts.offer((_YIELD,))
        self.wait_until(lambda: alerts.status == "Voice: Nhường đường" and not alerts._speaking)
        for offset in range(90):
            alerts.offer((replace(_YIELD, bbox=(20 + offset, 30, 40 + offset, 50)),))
        play.assert_called_once_with(13)
        alerts.offer((replace(_YIELD, bbox=(330, 30, 350, 50)),))
        self.wait_until(lambda: play.call_count == 2)

    def test_active_speech_drops_extra_requests_and_reset_stops_it(self) -> None:
        play = Mock(return_value=10)
        stop = Mock()
        alerts = VoiceAlerts(play=play, stop=stop)
        self.addCleanup(alerts.close)
        alerts.offer((_YIELD,))
        self.wait_until(lambda: alerts.status == "Voice: Nhường đường")
        for i in range(100):
            alerts.offer((replace(_YIELD, cnn_class_id=(i % 40), bbox=(300, 30, 350, 50)),))
        alerts.reset()
        self.wait_until(lambda: stop.called and not alerts._speaking)
        play.assert_called_once_with(13)

    def test_audio_failure_is_reported_without_retries_or_exceptions_to_the_ui(self) -> None:
        play = Mock(side_effect=RuntimeError("No audio device"))
        alerts = VoiceAlerts(play=play, stop=Mock())
        self.addCleanup(alerts.close)
        with self.assertLogs("src.traffic_sign_demo.voice_alerts", level="WARNING"):
            alerts.offer((_YIELD,))
            self.wait_until(lambda: alerts.status == "Voice unavailable")
        for _ in range(12):
            alerts.offer((_YIELD,))
        play.assert_called_once_with(13)
