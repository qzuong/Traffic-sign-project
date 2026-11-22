from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, get_ident
import unittest
from unittest.mock import Mock

import numpy as np

from src.traffic_sign_demo.alert_tracking import AlertTrack
from src.traffic_sign_demo.desktop_ui import DesktopVideoPlayer
from src.traffic_sign_demo.playback_controller import PlaybackEvent, PlaybackEventType
from src.traffic_sign_demo.simulation_events import DECISIONS, JsonlSimulationPublisher, SimulationSession
from src.traffic_sign_demo.tracked_voice_alerts import TrackedVoiceAlerts
from src.traffic_sign_demo.vietnamese_labels import VIETNAMESE_CLASSES
from src.traffic_sign_demo.vision import ClassifiedDetection, DisplayFrame


IMAGE = np.random.default_rng(42).integers(0, 255, (80, 180, 3), dtype=np.uint8)


def frame(ms=100, generation=7):
    return DisplayFrame(generation, ms, ms, 180, 80, IMAGE)


def track(track_id=1, label=13, blocked=None):
    value = AlertTrack(track_id, (5, 5, 30, 30), None, 100, 1, 1)
    value.confirmed = label
    value.speech_block = blocked
    value.votes.extend(((50, label, 0.8, blocked), (100, label, 0.9, blocked)))
    return value


SIGN = ClassifiedDetection((5, 5, 30, 30), 0, "traffic_sign", .8, 13, "Yield", 1)
SECOND_SIGN = replace(SIGN, bbox=(90, 5, 115, 30))


class SimulationSessionTests(unittest.TestCase):
    def setUp(self):
        self.publisher = Mock()
        self.session = SimulationSession(self.publisher)
        self.session.begin(7)

    def test_mapping_has_a_unique_semantic_event_and_label_for_every_class(self):
        self.assertEqual(set(DECISIONS), set(range(43)))
        self.assertEqual(len({decision.event_type for decision in DECISIONS.values()}), 43)
        for label in range(43):
            event = self.session.observe(frame(), track(label + 1, label))
            self.assertEqual(event.class_name_vi, VIETNAMESE_CLASSES[label])
            self.assertEqual(event.event_type, DECISIONS[label].event_type)
        self.assertEqual(DECISIONS[7].parameters, (("limit_kmh", 100),))
        self.assertEqual(DECISIONS[33].event_type, "TURN_RIGHT_ONLY")

    def test_schema_uses_video_position_and_separate_utc_creation_time(self):
        item = asdict(self.session.observe(frame(123), track()))
        self.assertEqual(item["schema_version"], "1.0")
        self.assertEqual(item["event_id"], f"{item['session_id']}:track-1")
        self.assertEqual(item["video_timestamp_ms"], 123)
        self.assertEqual(item["source_frame_id"], 123)
        self.assertIs(item["confirmed"], True)
        self.assertEqual(item["decision_status"], "confirmed")
        self.assertEqual(datetime.fromisoformat(item["created_at"]).utcoffset().total_seconds(), 0)
        self.assertEqual(item["evidence"]["observation_count"], 2)
        self.assertEqual(item["evidence"]["bbox_frame_size"], (180, 80))

    def test_unconfirmed_observation_never_publishes(self):
        self.assertIsNone(self.session.observe(frame(), track(label=None)))
        self.publisher.publish_simulation_event.assert_not_called()

    def test_aggregation_confirmed_but_withheld_has_no_action(self):
        event = self.session.observe(frame(), track(label=7, blocked="speed_face_unverified"))
        self.assertEqual(event.event_type, "SPEED_LIMIT_100")
        self.assertTrue(event.confirmed)
        self.assertEqual(event.decision_status, "withheld")
        self.assertIsNone(event.suggested_action)
        self.assertEqual(event.parameters, {})
        self.assertEqual(event.evidence.speech_evidence_block, "speed_face_unverified")

    def test_repeated_callback_and_changed_label_share_one_track_identity(self):
        same = track()
        self.session.observe(frame(), same)
        self.session.observe(frame(), same)
        same.confirmed = 17
        self.session.observe(frame(120), same)
        self.publisher.publish_simulation_event.assert_called_once()

    def test_two_tracks_with_same_class_each_publish(self):
        first = self.session.observe(frame(), track(1))
        second = self.session.observe(frame(), track(2))
        self.assertNotEqual(first.event_id, second.event_id)
        self.assertEqual(first.class_id, second.class_id)

    def test_rebind_preserves_session_and_rejects_obsolete_results(self):
        same = track()
        first = self.session.observe(frame(), same)
        self.session.rebind(8)
        self.assertIsNone(self.session.observe(frame(generation=7), track(2)))
        self.assertIsNone(self.session.observe(frame(generation=8), same))
        self.assertIsNone(self.session.observe(frame(ms=99, generation=8), track(3)))
        self.assertEqual(self.session.observe(frame(generation=8), track(2)).session_id, first.session_id)

    def test_callback_and_json_events_continue_when_audio_worker_fails(self):
        entered = Event()
        def fail(_):
            entered.set()
            raise RuntimeError("test audio failure")
        alerts = TrackedVoiceAlerts(play=fail, stop=Mock(), on_confirmation=self.session.observe)
        try:
            with self.assertLogs("src.traffic_sign_demo.tracked_voice_alerts", "WARNING"):
                alerts.observe(frame(100), (SIGN,))
                alerts.observe(frame(200), (SIGN,))
                self.assertTrue(entered.wait(2))
                with alerts._condition:
                    self.assertTrue(alerts._condition.wait_for(lambda: alerts._failed, timeout=2))
            alerts.observe(frame(250), (SECOND_SIGN,))
            alerts.observe(frame(350), (SECOND_SIGN,))
            self.assertEqual(self.publisher.publish_simulation_event.call_count, 2)
            self.assertEqual(alerts.diagnostics["played"], 0)
        finally:
            alerts.close()

    def test_expired_voice_alert_remains_exported_as_confirmed_event(self):
        entered, release = Event(), Event()
        def play(_):
            entered.set()
            release.wait(2)
            return 0
        with TemporaryDirectory() as tmp:
            exporter = JsonlSimulationPublisher(Path(tmp))
            self.session.publisher = exporter
            alerts = TrackedVoiceAlerts(play=play, stop=Mock(), on_confirmation=self.session.observe)
            try:
                alerts.observe(frame(100), (SIGN,))
                alerts.observe(frame(200), (SIGN,))
                self.assertTrue(entered.wait(2))
                alerts.observe(frame(250), (SECOND_SIGN,))
                alerts.observe(frame(350), (SECOND_SIGN,))
                alerts.observe(frame(1500), ())
                self.assertEqual(alerts.diagnostics["expired"], 1)
            finally:
                release.set()
                alerts.close()
                exporter.close()
                self.assertTrue(exporter.done.wait(2))
            events = [json.loads(line) for line in next(Path(tmp).glob("*.jsonl")).read_text(encoding="utf8").splitlines()]
            self.assertEqual([e["track_id"] for e in events], [1, 2])
            self.assertEqual([e["decision_status"] for e in events], ["confirmed", "confirmed"])


class SimulationExportTests(unittest.TestCase):
    def test_jsonl_order_unicode_validation_and_distinct_files(self):
        with TemporaryDirectory() as tmp:
            publisher = JsonlSimulationPublisher(Path(tmp))
            session = SimulationSession(publisher)
            session.begin(7)
            first = session.observe(frame(), track())
            session.observe(frame(125), track(2, 12))
            session.begin(8)
            second = session.observe(frame(generation=8), track())
            publisher.close()
            self.assertTrue(publisher.done.wait(2))
            self.assertNotEqual(first.session_id, second.session_id)
            path = Path(tmp) / f"session-{first.session_id}.jsonl"
            raw = path.read_text(encoding="utf8")
            self.assertIn("Nhường đường", raw)
            self.assertEqual([json.loads(line)["video_timestamp_ms"] for line in raw.splitlines()], [100, 125])
            self.assertEqual(len(list(Path(tmp).glob("*.jsonl"))), 2)
            self.assertEqual(publisher.failures, 0)

    def test_disk_failure_is_reported_and_close_drains(self):
        with TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "not-directory"
            blocked.write_bytes(b"keep")
            publisher = JsonlSimulationPublisher(blocked)
            session = SimulationSession(publisher)
            session.begin(7)
            with self.assertLogs("src.traffic_sign_demo.simulation_events", "ERROR"):
                self.assertIsNotNone(session.observe(frame(), track()))
                publisher.close()
                self.assertTrue(publisher.done.wait(2))
            self.assertEqual(publisher.failures, 1)
            self.assertEqual(blocked.read_bytes(), b"keep")


class SimulationUiTests(unittest.TestCase):
    def setUp(self):
        self.player = object.__new__(DesktopVideoPlayer)
        self.player._alerts = Mock()
        self.player._tracker = Mock()
        self.player._simulation = SimulationSession(Mock())
        self.player.simulation_var = Mock()
        self.player.simulation_sign_var = Mock()
        self.player.simulation_event_type_var = Mock()
        self.player.simulation_action_var = Mock()
        self.player.simulation_image_label = Mock()
        self.player._set_simulation_sign_image = Mock()
        self.player.inference = Mock(session_id=7)
        self.player._frame_buffer = []
        self.player._buffered_results = {}
        self.player._display_times = []
        self.player._overlay_drop_log_times = {}
        self.player._overlay_rejection_counts = {}
        self.player._update_ai_metrics = Mock()

    def test_replay_seek_and_open_restart_session_and_clear_panel(self):
        ids = set()
        for kind in (PlaybackEventType.OPEN_NEW_VIDEO, PlaybackEventType.REPLAY,
                     PlaybackEventType.SEEK, PlaybackEventType.OPEN_NEW_VIDEO):
            self.player._invalidate_ai(PlaybackEvent(kind, Path("test.mp4"), 0))
            self.assertIsNone(self.player._simulation.last_event)
            ids.add(self.player._simulation.session_id)
            self.player._observe_simulation_event(frame(), track())
        self.assertEqual(len(ids), 4)

    def test_stop_clears_session_and_delayed_callback_cannot_update_panel(self):
        self.player._simulation.begin(7)
        self.player._invalidate_ai(PlaybackEvent(PlaybackEventType.STOP, Path("test.mp4"), 0))
        self.assertIsNone(self.player._simulation.session_id)
        self.player.simulation_var.reset_mock()
        self.player.simulation_sign_var.reset_mock()
        self.player.simulation_event_type_var.reset_mock()
        self.player.simulation_action_var.reset_mock()
        self.player._set_simulation_sign_image.reset_mock()
        self.player._observe_simulation_event(frame(), track())
        self.player.simulation_var.set.assert_not_called()
        self.player.simulation_sign_var.set.assert_not_called()
        self.player.simulation_event_type_var.set.assert_not_called()
        self.player.simulation_action_var.set.assert_not_called()
        self.player._set_simulation_sign_image.assert_not_called()

    def test_confirmation_updates_panel_on_the_observation_thread(self):
        thread = get_ident()
        def check(text):
            self.assertEqual(get_ident(), thread)
            self.assertIn("Biển báo: Nhường đường", text)
            self.assertIn("YIELD_SIGN", text)
            self.assertIn("Đề xuất: Chuẩn bị nhường đường", text)
            self.assertNotIn("Track ID", text)
        self.player.simulation_var.set.side_effect = check
        self.player._simulation.begin(7)
        alerts = TrackedVoiceAlerts(on_confirmation=self.player._observe_simulation_event,
                                    play=Mock(return_value=0), stop=Mock())
        try:
            alerts.observe(frame(100), (SIGN,))
            alerts.observe(frame(200), (SIGN,))
            self.player.simulation_var.set.assert_called_once()
            self.player.simulation_sign_var.set.assert_called_once_with("Nhường đường")
            self.player.simulation_event_type_var.set.assert_called_once_with("YIELD_SIGN")
            self.player.simulation_action_var.set.assert_called_once_with(
                "Chuẩn bị nhường đường"
            )
            self.player._set_simulation_sign_image.assert_called_once_with(13)
        finally:
            alerts.close()

    def test_unconfirmed_or_withheld_event_does_not_replace_empty_panel(self):
        self.player._simulation.begin(7)
        self.player._observe_simulation_event(frame(), track(label=None))
        self.player.simulation_var.set.assert_not_called()

        self.player._observe_simulation_event(
            frame(), track(label=7, blocked="speed_face_unverified")
        )

        self.player.simulation_var.set.assert_not_called()
        self.player._set_simulation_sign_image.assert_not_called()

    def test_event_panel_contains_only_sign_semantic_type_and_action(self):
        self.player._simulation.begin(7)

        self.player._observe_simulation_event(frame(), track())

        text = self.player.simulation_var.set.call_args.args[0]
        self.assertEqual(
            text,
            "Biển báo: Nhường đường\n\n"
            "Event: YIELD_SIGN\n\n"
            "Đề xuất: Chuẩn bị nhường đường",
        )
        self.assertNotIn("Track ID", text)
        self.assertNotIn("Simulator:", text)

    def test_confirmed_event_without_an_image_keeps_event_details(self):
        self.player.root = Mock()
        self.player._simulation_image_cache = {}
        self.player._active_simulation_image = None
        self.player._simulation_image_directory = Path("missing-sign-images")
        self.player._set_simulation_sign_image = (
            lambda class_id: DesktopVideoPlayer._set_simulation_sign_image(
                self.player, class_id
            )
        )
        self.player._simulation.begin(7)

        with self.assertLogs("src.traffic_sign_demo.desktop_ui", "WARNING"):
            self.player._observe_simulation_event(frame(), track())

        self.player.simulation_sign_var.set.assert_called_once_with("Nhường đường")
        self.player.simulation_event_type_var.set.assert_called_once_with("YIELD_SIGN")
        self.player.simulation_action_var.set.assert_called_once_with(
            "Chuẩn bị nhường đường"
        )
        self.player.simulation_image_label.configure.assert_called_once_with(
            image="", text="—"
        )
