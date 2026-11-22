from dataclasses import replace
import threading
import time
import unittest
from unittest.mock import Mock

import numpy as np

from src.traffic_sign_demo.alert_tracking import AlertTracks
from src.traffic_sign_demo.tracked_voice_alerts import TrackedVoiceAlerts
from src.traffic_sign_demo.voice_alerts import ClipTiming
from src.traffic_sign_demo.vision import ClassifiedDetection, DisplayFrame


_PATTERN = np.random.default_rng(12).integers(20, 235, (24, 24, 3), dtype=np.uint8)
_DETECTION = ClassifiedDetection((0, 0, 24, 24), 0, "traffic_sign", 0.8, 13, "Yield", 1)


def observation(ms, *signs, pattern=_PATTERN):
    image = np.zeros((90, 420, 3), dtype=np.uint8)
    detections = []
    for x, label in signs:
        image[30:54, x:x + 24] = pattern
        detections.append(replace(_DETECTION, bbox=(x, 30, x + 24, 54), cnn_class_id=label))
    return DisplayFrame(1, ms, ms, 420, 90, image), tuple(detections)


def update(tracker, ms, *signs, **kwargs):
    return tracker.update(*observation(ms, *signs, **kwargs), time.monotonic())


class AlertIdentityTests(unittest.TestCase):
    def test_two_same_class_signs_remain_separate_across_motion(self):
        tracks = AlertTracks()
        initial = update(tracks, 0, (22, 13), (155, 13))
        moved = update(tracks, 350, (42, 13), (177, 13))
        self.assertEqual([t.id for t in initial], [t.id for t in moved])
        self.assertEqual([t.confirmed for t in moved], [13, 13])
        self.assertNotEqual(moved[0].id, moved[1].id)

    def test_short_missing_observation_survives_but_long_gap_expires(self):
        tracks = AlertTracks()
        original, = update(tracks, 0, (35, 13))
        update(tracks, 300)
        same, = update(tracks, 650, (56, 13))
        self.assertEqual(same.id, original.id)
        later, = update(tracks, 1600, (56, 13))
        self.assertNotEqual(later.id, original.id)
        self.assertEqual(tracks.lost, 1)
        self.assertIsNone(later.confirmed)

    def test_conflict_and_duplicate_frame_do_not_confirm(self):
        tracks = AlertTracks()
        first, = update(tracks, 0, (35, 13))
        self.assertIsNone(first.confirmed)
        self.assertEqual(update(tracks, 0, (35, 13)), [])
        conflict, = update(tracks, 280, (40, 17))
        self.assertEqual(conflict.id, first.id)
        self.assertIsNone(conflict.confirmed)
        majority, = update(tracks, 560, (45, 13))
        self.assertEqual(majority.confirmed, 13)

    def test_different_appearance_does_not_inherit_prior_votes(self):
        tracks = AlertTracks()
        prior, = update(tracks, 0, (35, 13))
        different, = update(tracks, 360, (35, 13), pattern=255 - _PATTERN)
        self.assertNotEqual(prior.id, different.id)
        self.assertIsNone(different.confirmed)

    def test_small_crop_jitter_preserves_identity(self):
        tracks = AlertTracks()
        first, = update(tracks, 0, (35, 13))
        frame, (detection,) = observation(300, (35, 13))
        later, = tracks.update(frame, (replace(detection, bbox=(37, 31, 61, 55)),), time.monotonic())
        self.assertEqual(later.id, first.id)
        self.assertEqual(later.confirmed, 13)

    def test_equally_plausible_tracks_do_not_inherit_votes(self):
        tracks = AlertTracks()
        first = update(tracks, 0, (22, 13), (50, 13))
        uncertain, = update(tracks, 300, (36, 13))
        self.assertNotIn(uncertain.id, {t.id for t in first})
        self.assertIsNone(uncertain.confirmed)
        self.assertGreater(tracks.ambiguous, 0)


class TrackedVoiceTests(unittest.TestCase):
    def test_speech_veto_leaves_confirmation_visible_and_needs_two_eligible_votes(self):
        play = Mock(return_value=0)
        alerts = TrackedVoiceAlerts(play=play, stop=Mock())
        self.addCleanup(alerts.close)
        for ms, veto in ((0, "speed_face_unverified"), (150, "speed_face_unverified"),
                         (300, None), (450, None)):
            frame, (detection,) = observation(ms, (25, 4))
            matches = alerts.observe(frame, (replace(detection, speech_veto=veto),))
            if ms in (150, 300):
                self.assertEqual(matches[0][2], 4)
                self.assertEqual(alerts.diagnostics["accepted"], 0)
                play.assert_not_called()
        self.wait_for(lambda: alerts.diagnostics["played"] == 1)
        play.assert_called_once_with(4)
        self.assertEqual(alerts.diagnostics["tracks_with_speech_suppression"], 1)
        self.assertEqual(alerts.diagnostics["speech_suppressed_speed_face_unverified"], 1)

    def test_pending_alert_cannot_start_after_latest_crop_is_vetoed(self):
        alerts, release, calls = self.busy_voice()
        for ms in (450, 550):
            alerts.observe(*observation(ms, (205, 38)))
        frame, (detection,) = observation(650, (205, 38))
        alerts.observe(frame, (replace(detection, speech_veto="mandatory_blue_face_unverified"),))
        release.set()
        self.wait_for(lambda: alerts.diagnostics["played"] == 1)
        self.assertEqual(calls, [13])
        self.assertEqual(alerts.diagnostics["pending"], 1)
        self.assertTrue(any(row["event"] == "speech_suppressed" for row in alerts.trace))
        alerts.observe(*observation(1420))
        self.assertEqual(alerts.diagnostics["pending"], 0)
        self.assertEqual(alerts.diagnostics["expired"], 1)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Voice worker did not reach the expected state.")

    def busy_voice(self, capacity=3, **kwargs):
        release = threading.Event()
        calls = []
        def play(class_id):
            calls.append(class_id)
            if len(calls) == 1:
                release.wait(2)
            return 0
        alerts = TrackedVoiceAlerts(capacity=capacity, play=play, stop=Mock(), **kwargs)
        self.addCleanup(alerts.close)
        self.addCleanup(release.set)
        alerts.observe(*observation(0, (25, 13)))
        alerts.observe(*observation(300, (30, 13)))
        self.wait_for(lambda: calls == [13])
        return alerts, release, calls

    def test_same_class_new_sign_can_wait_while_audio_is_busy(self):
        alerts, release, calls = self.busy_voice()
        alerts.observe(*observation(450, (35, 13), (200, 13)))
        alerts.observe(*observation(650, (39, 13), (205, 13)))
        self.assertEqual(alerts.diagnostics["pending"], 1)
        self.assertEqual(alerts.diagnostics["duplicates_suppressed"], 2)
        release.set()
        self.wait_for(lambda: calls == [13, 13])

    def test_class_fluctuations_do_not_rearm_a_track(self):
        alerts, release, calls = self.busy_voice()
        for index in range(1, 7):
            alerts.observe(*observation(300 + index * 150, (30 + index, 17)))
        release.set()
        self.assertEqual(alerts.diagnostics["generated"], 1)
        self.assertEqual(alerts.diagnostics["pending"], 0)

    def test_media_time_expires_alert_before_previous_clip_finishes(self):
        alerts, release, calls = self.busy_voice()
        alerts.observe(*observation(450, (205, 14)))
        alerts.observe(*observation(650, (210, 14)))
        self.assertEqual(alerts.diagnostics["pending"], 1)
        alerts.observe(*observation(1400))
        self.assertEqual(alerts.diagnostics["expired"], 1)
        self.assertEqual(alerts.diagnostics["pending"], 0)
        release.set()
        self.assertEqual(calls, [13])

    def test_priority_overflow_is_bounded_and_keeps_urgent_sign(self):
        alerts, release, calls = self.busy_voice(capacity=1)
        alerts.observe(*observation(450, (105, 35), (210, 14), (315, 38)))
        alerts.observe(*observation(650, (110, 35), (215, 14), (320, 38)))
        self.assertEqual(alerts.diagnostics["peak_queue"], 1)
        self.assertEqual(alerts.diagnostics["overflow"], 2)
        release.set()
        self.wait_for(lambda: calls == [13, 14])

    def test_urgent_first_then_fifo_for_equal_priority(self):
        alerts, release, calls = self.busy_voice()
        alerts.observe(*observation(450, (105, 35)))
        alerts.observe(*observation(550, (105, 35), (210, 38), (315, 14)))
        alerts.observe(*observation(650, (105, 35), (210, 38), (315, 14)))
        release.set()
        self.wait_for(lambda: len(calls) == 4)
        self.assertEqual(calls, [13, 14, 35, 38])

    def test_current_older_alert_survives_long_audio_and_ages_ahead_of_urgent(self):
        now = Mock(return_value=100.0)
        alerts, release, calls = self.busy_voice(clock=now)
        for step in range(1, 11):
            now.return_value = 100 + step * 0.35
            signs = [(100, 35)]
            if step >= 9:
                signs.append((250, 14))
            alerts.observe(*observation(300 + step * 350, *signs))
        self.assertEqual(alerts.diagnostics["pending"], 2)
        release.set()
        self.wait_for(lambda: alerts.diagnostics["played"] == 3)
        self.assertEqual(calls, [13, 35, 14])
        self.assertGreater(alerts.diagnostics["measurements"][1]["queue_ms"], 2200)

    def test_transient_uncertainty_defers_dispatch_until_same_label_recovers(self):
        alerts, release, calls = self.busy_voice()
        for ms, label in ((450, 14), (650, 14), (800, 17), (950, 17)):
            alerts.observe(*observation(ms, (205, label)))
        release.set()
        self.wait_for(lambda: alerts.diagnostics["played"] == 1)
        self.assertEqual(alerts.diagnostics["pending"], 1)
        self.assertEqual(calls, [13])
        for ms in (1000, 1050, 1100, 1150):
            alerts.observe(*observation(ms, (205, 14)))
        self.wait_for(lambda: len(calls) == 2)
        self.assertEqual(calls, [13, 14])
        self.assertEqual(alerts.diagnostics["generated"], 2)

    def test_expired_pending_track_is_never_requeued_even_if_seen_again(self):
        alerts, release, calls = self.busy_voice()
        for ms in (450, 550):
            alerts.observe(*observation(ms, (205, 14)))
        alerts.observe(*observation(1270))
        self.assertEqual(alerts.diagnostics["expired_sign_stale"], 1)
        alerts.observe(*observation(1300, (205, 14)))
        release.set()
        self.assertEqual(alerts.diagnostics["generated"], 2)
        self.assertEqual(alerts.diagnostics["pending"], 0)
        self.assertEqual(calls, [13])

    def test_outward_motion_retires_a_sign_before_the_generic_freshness_limit(self):
        alerts, release, calls = self.busy_voice()
        for ms, x in ((450, 378), (600, 390)):
            alerts.observe(*observation(ms, (x, 14)))
        alerts.observe(*observation(1050))
        self.assertEqual(alerts.diagnostics["expired_sign_left_view"], 1)
        release.set()
        self.assertEqual(calls, [13])

    def test_quiet_tail_stops_before_starting_the_next_alert(self):
        backend = Mock()
        backend.play.side_effect = [ClipTiming(0.6, 0.05), ClipTiming(0, 0)]
        alerts = TrackedVoiceAlerts(play=backend.play, stop=backend.stop)
        self.addCleanup(alerts.close)
        for ms in (0, 300):
            alerts.observe(*observation(ms, (25, 13), (205, 14)))
        self.wait_for(lambda: alerts.diagnostics["played"] == 2)
        self.assertEqual([call[0] for call in backend.mock_calls], ["play", "stop", "play"])
        self.assertEqual(alerts.diagnostics["measurements"][0]["wav_ms"], 600)
        self.assertEqual(alerts.diagnostics["measurements"][0]["slot_ms"], 50)

    def test_confirmed_different_label_retires_the_old_pending_warning(self):
        alerts, release, calls = self.busy_voice()
        for ms, label in ((450, 14), (550, 14), (650, 17), (750, 17), (850, 17), (950, 17)):
            alerts.observe(*observation(ms, (205, label)))
        self.assertEqual(alerts.diagnostics["expired_label_changed"], 1)
        release.set()
        self.assertEqual(alerts.diagnostics["pending"], 0)
        self.assertEqual(calls, [13])

    def test_trace_keeps_detection_clock_and_video_position_separate(self):
        clock = Mock(return_value=100.0)
        alerts = TrackedVoiceAlerts(play=Mock(return_value=0), stop=Mock(), clock=clock)
        self.addCleanup(alerts.close)
        frame, (detection,) = observation(1000, (25, 13))
        alerts.observe(frame, (replace(detection, valid_yolo_at=99.6, valid_cnn_at=99.8),))
        clock.return_value = 100.2
        alerts.observe(*observation(1200, (25, 13)))
        self.wait_for(lambda: alerts.diagnostics["played"] == 1)
        events = {event["event"]: event for event in alerts.trace}
        self.assertEqual(events["yolo_valid"]["video_ms"], 1000)
        self.assertEqual(events["yolo_valid"]["monotonic"], 99.6)
        self.assertEqual(events["cnn_valid"]["monotonic"], 99.8)
        self.assertEqual(events["track_created"]["monotonic"], 100)
        for name in ("confirmed", "offered", "accepted", "audio_started"):
            self.assertEqual(events[name]["video_ms"], 1200)
        self.assertAlmostEqual(alerts.diagnostics["speech_latency_ms"][0], 600)

    def test_stalled_display_never_releases_queued_alert(self):
        now = Mock(return_value=100.0)
        alerts, release, calls = self.busy_voice(clock=now)
        for ms in (450, 550):
            alerts.observe(*observation(ms, (205, 14)))
        now.return_value += 1
        release.set()
        self.wait_for(lambda: alerts.diagnostics.get("expired_video_stalled", 0) == 1)
        self.assertEqual(calls, [13])

    def test_end_of_video_clears_pending_and_lets_active_clip_finish(self):
        alerts, release, calls = self.busy_voice()
        for ms in (450, 550):
            alerts.observe(*observation(ms, (205, 14)))
        alerts.complete()
        alerts.observe(*observation(650, (205, 14)))
        self.assertEqual(alerts.diagnostics["pending"], 0)
        release.set()
        self.wait_for(lambda: any(row["event"] == "audio_finished" for row in alerts.trace))
        alerts._stop.assert_not_called()
        self.assertEqual(calls, [13])
        self.assertIn("end_of_video", {row.get("reason") for row in alerts.trace})

    def test_playback_discontinuities_cancel_pending_and_active_audio(self):
        for reason in ("stop", "replay", "seek", "open_new_video"):
            with self.subTest(reason=reason):
                alerts, release, calls = self.busy_voice()
                for ms in (450, 550):
                    alerts.observe(*observation(ms, (205, 14)))
                alerts.reset(reason)
                release.set()
                self.wait_for(lambda: any(row["event"] == "audio_cancelled" for row in alerts.trace))
                alerts._stop.assert_called_once()
                self.assertEqual(calls, [13])
                self.assertEqual(alerts.diagnostics["pending"], 0)
                reasons = [row["reason"] for row in alerts.trace
                           if row["event"] in {"cancelled", "audio_cancelled"}]
                self.assertEqual(reasons, [reason, reason])

    def test_suspend_preserves_spoken_identity_and_session_reset_clears_it(self):
        play, stop = Mock(return_value=20), Mock()
        alerts = TrackedVoiceAlerts(play=play, stop=stop)
        self.addCleanup(alerts.close)
        alerts.observe(*observation(0, (25, 13)))
        alerts.observe(*observation(300, (30, 13)))
        self.wait_for(lambda: alerts.diagnostics.get("played") == 1)
        alerts.suspend()
        self.wait_for(lambda: stop.called)
        alerts.observe(*observation(400, (35, 13)))
        self.assertEqual(alerts.diagnostics["generated"], 1)
        alerts.reset()
        alerts.observe(*observation(0, (25, 13)))
        alerts.observe(*observation(300, (30, 13)))
        self.wait_for(lambda: play.call_count == 2)

    def test_tracked_voice_reports_audio_failure(self):
        play = Mock(side_effect=RuntimeError("audio unavailable"))
        alerts = TrackedVoiceAlerts(play=play, stop=Mock())
        self.addCleanup(alerts.close)
        with self.assertLogs("src.traffic_sign_demo.tracked_voice_alerts", level="WARNING"):
            alerts.observe(*observation(0, (25, 13)))
            alerts.observe(*observation(300, (30, 13)))
            self.wait_for(lambda: alerts.status == "Voice unavailable")
        alerts.observe(*observation(500, (40, 13)))
        play.assert_called_once_with(13)
        self.assertEqual(alerts.diagnostics["played"], 0)
        self.assertIn("audio_error", [row["event"] for row in alerts.trace])
