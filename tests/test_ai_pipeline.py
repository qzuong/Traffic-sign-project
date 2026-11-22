import base64
from collections import deque
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from src.traffic_sign_demo.class_mapping import load_class_mapping
from src.traffic_sign_demo.desktop_ui import DesktopVideoPlayer
from src.traffic_sign_demo import yolo_worker
from src.traffic_sign_demo.inference_service import (
    GTSDB_SHA256,
    InferenceService,
    InferenceServiceError,
    _JsonLineWorker,
)
from src.traffic_sign_demo.playback_controller import PlaybackEventType, PlaybackState
from src.traffic_sign_demo.video_reader import VideoReader
from src.traffic_sign_demo.vision import (
    ClassifiedDetection,
    DisplayFrame,
    InferenceResult,
    clip_bbox,
    draw_overlay,
    overlay_rejection_reason,
    preprocess_crop,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeWorker:
    def __init__(
        self,
        kind: str,
        on_yolo_started: threading.Event | None = None,
        release_yolo: threading.Event | None = None,
        no_detections: bool = False,
    ) -> None:
        self.kind = kind
        self.on_yolo_started = on_yolo_started
        self.release_yolo = release_yolo
        self.no_detections = no_detections
        self.requests: list[dict[str, object]] = []

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append(payload)
        if self.kind == "yolo":
            if self.on_yolo_started is not None:
                self.on_yolo_started.set()
            if self.release_yolo is not None:
                if not self.release_yolo.wait(timeout=5):
                    raise TimeoutError("Test did not release fake YOLO.")
            return {
                "type": "result",
                "session_id": payload["session_id"],
                "frame_id": payload["frame_id"],
                "timestamp_ms": payload["timestamp_ms"],
                "detections": [] if self.no_detections else [
                    {
                        "bbox": [1.0, 1.0, 3.0, 3.0],
                        "class_id": 11,
                        "class_name": "No Entry",
                        "confidence": 0.8,
                    },
                    {
                        "bbox": [8.0, 8.0, 9.0, 9.0],
                        "class_id": 11,
                        "class_name": "No Entry",
                        "confidence": 0.7,
                    },
                ],
            }

        return {
            "type": "result",
            "session_id": payload["session_id"],
            "frame_id": payload["frame_id"],
            "timestamp_ms": payload["timestamp_ms"],
            "classifications": [
                {
                    "detection_index": index,
                    "class_id": 17,
                    "class_name": "No entry",
                    "score": 0.8,
                }
                for index, _tensor in enumerate(payload["tensors"])
            ],
        }

    def terminate(self) -> None:
        pass


class VisionPreprocessingTests(unittest.TestCase):
    def test_bbox_clips_to_frame_and_rejects_invalid_boxes(self) -> None:
        self.assertEqual(clip_bbox((-1.2, 1.1, 4.2, 5.0), 4, 4), (0, 1, 4, 4))
        self.assertIsNone(clip_bbox((4, 1, 5, 2), 4, 4))
        self.assertIsNone(clip_bbox((2, 2, 1, 3), 4, 4))
        self.assertIsNone(clip_bbox((0, 0, float("nan"), 2), 4, 4))
        self.assertIsNone(clip_bbox((0, 0, 2), 4, 4))
        self.assertIsNone(clip_bbox(np.array(1.0), 4, 4))

    def test_preprocessing_matches_rgb_30_by_30_float32_normalization(self) -> None:
        crop = np.zeros((5, 7, 3), dtype=np.uint8)
        crop[:, :, 0] = 10
        crop[:, :, 1] = 20
        crop[:, :, 2] = 30

        processed = preprocess_crop(crop)

        self.assertEqual(processed.shape, (1, 30, 30, 3))
        self.assertEqual(processed.dtype, np.float32)
        np.testing.assert_allclose(
            processed[0, 0, 0], np.array([30, 20, 10], dtype=np.float32) / 255.0
        )

    def test_class_mapping_is_loaded_from_project_training_script(self) -> None:
        mapping = load_class_mapping(PROJECT_ROOT / "models" / "model.py")

        self.assertEqual(len(mapping), 43)
        self.assertEqual(mapping[15], "No vehicles")
        self.assertEqual(mapping[17], "No entry")

    def test_overlay_scales_source_coordinates_to_display_coordinates(self) -> None:
        detection = ClassifiedDetection(
            bbox=(20.0, 20.0, 40.0, 40.0),
            yolo_class_id=1,
            yolo_class_name="debug",
            yolo_confidence=0.8,
            cnn_class_id=17,
            cnn_class_name="No entry",
            cnn_score=0.9,
        )
        display = np.zeros((40, 40, 3), dtype=np.uint8)

        overlay = draw_overlay(display, (detection,), source_width=80, source_height=80)

        np.testing.assert_array_equal(overlay[10, 10], np.array([40, 220, 40]))
        np.testing.assert_array_equal(display, np.zeros_like(display))

    def test_no_detections_produce_no_overlay(self) -> None:
        display = np.zeros((40, 40, 3), dtype=np.uint8)

        overlay = draw_overlay(display, (), source_width=80, source_height=80)

        np.testing.assert_array_equal(overlay, display)

    def test_overlay_freshness_requires_exact_session_frame_and_timestamp(self) -> None:
        result = InferenceResult(
            session_id=5,
            frame_id=7,
            timestamp_ms=233.3,
            submitted_monotonic=9.88,
            completed_monotonic=10.0,
            elapsed_ms=120.0,
            detections=(),
        )

        self.assertIsNone(
            overlay_rejection_reason(result, 5, 7, 233.3, 10.1, max_age_ms=500)
        )
        self.assertEqual(
            overlay_rejection_reason(result, 6, 7, 233.3, 10.1, 500),
            "different playback session",
        )
        self.assertEqual(
            overlay_rejection_reason(result, 5, 8, 233.3, 10.1, 500),
            "different frame",
        )
        self.assertEqual(
            overlay_rejection_reason(result, 5, 7, 240.0, 10.1, 500),
            "different video timestamp",
        )
        self.assertEqual(
            overlay_rejection_reason(result, 5, 7, 233.3, 10.6, 700),
            "expired (720 ms old)",
        )


class InferenceServiceTests(unittest.TestCase):
    def test_cnn_resolution_skips_a_python_without_tensorflow(self) -> None:
        service = InferenceService(project_root=PROJECT_ROOT)
        self.addCleanup(service.close)
        wrong_python = PROJECT_ROOT / ".venv-yolo" / "python.exe"
        cnn_python = PROJECT_ROOT / ".venv-cnn" / "python.exe"
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(service, "_worker_python_candidates", return_value=[wrong_python, cnn_python]),
            patch.object(service, "_probe_worker_python", side_effect=["missing tensorflow", None]) as probe,
        ):
            self.assertEqual(service._python_for_worker("cnn"), str(cnn_python))
        self.assertEqual([call.args for call in probe.call_args_list], [
            (wrong_python, ("numpy", "tensorflow")),
            (cnn_python, ("numpy", "tensorflow")),
        ])

    def test_explicit_worker_overrides_are_validated_without_falling_back(self) -> None:
        service = InferenceService(project_root=PROJECT_ROOT)
        self.addCleanup(service.close)
        override = PROJECT_ROOT / "configured-python.exe"
        for name, modules in (("cnn", ("numpy", "tensorflow")),
                              ("yolo", ("numpy", "cv2", "torch", "ultralytics"))):
            key = f"TRAFFIC_SIGN_{name.upper()}_PYTHON"
            with (
                self.subTest(worker=name),
                patch.dict(os.environ, {key: str(override)}),
                patch.object(service, "_worker_python_candidates") as defaults,
                patch.object(service, "_probe_worker_python", return_value="missing " + modules[-1]) as probe,
            ):
                with self.assertRaisesRegex(InferenceServiceError, key + ".*" + modules[-1]):
                    service._python_for_worker(name)
                defaults.assert_not_called()
                probe.assert_called_once_with(override, modules)

    def test_python_dependency_probe_detects_a_missing_module(self) -> None:
        service = InferenceService(project_root=PROJECT_ROOT)
        self.addCleanup(service.close)
        result = service._probe_worker_python(
            Path(sys.executable), ("json", "_traffic_sign_missing_test_module")
        )
        self.assertEqual(result, "missing _traffic_sign_missing_test_module")

    def test_detector_selection_keeps_original_and_pins_candidate(self) -> None:
        for detector, relative_path in (
            ("original", "models/traffic_sign_yolo.pt"),
            ("gtsdb", "models/candidates/gtsdb_yolov8n.pt"),
        ):
            with self.subTest(detector=detector):
                factory = Mock(side_effect=lambda kind, *_: FakeWorker(kind, no_detections=True))
                service = InferenceService(
                    project_root=PROJECT_ROOT, detector=detector, worker_factory=factory
                )
                try:
                    service.submit(np.zeros((4, 4, 3), dtype=np.uint8), 0, 0)
                    self.wait_for_result(service)
                    arguments = factory.call_args.args[1]
                    self.assertEqual(Path(arguments[arguments.index("--model") + 1]),
                                     PROJECT_ROOT / relative_path)
                    if detector == "gtsdb":
                        self.assertEqual(arguments[arguments.index("--verified-sha256") + 1], GTSDB_SHA256)
                    else:
                        self.assertNotIn("--verified-sha256", arguments)
                finally:
                    service.close()

    def test_worker_rejects_modified_candidate_before_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "modified.pt"
            path.write_bytes(b"modified")
            output = io.StringIO()
            with (
                patch.object(sys, "argv", ["worker", "--model", str(path), "--verified-sha256", GTSDB_SHA256]),
                redirect_stdout(output),
            ):
                yolo_worker.main()
            message = json.loads(output.getvalue())
            self.assertEqual(message["type"], "error")
            self.assertIn("approved SHA-256", message["error"])

    def make_service(
        self,
        yolo_started: threading.Event | None = None,
        release_yolo: threading.Event | None = None,
        no_detections: bool = False,
    ) -> tuple[InferenceService, dict[str, FakeWorker]]:
        clients: dict[str, FakeWorker] = {}

        def worker_factory(
            kind: str, _arguments: list[str], _working_directory: Path
        ) -> FakeWorker:
            worker = FakeWorker(
                kind, yolo_started, release_yolo, no_detections=no_detections
            )
            clients[kind] = worker
            return worker

        service = InferenceService(
            project_root=PROJECT_ROOT,
            worker_factory=worker_factory,
        )
        return service, clients

    def wait_for_result(self, service: InferenceService):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = service.poll_result()
            if result is not None:
                return result
            if service.status.startswith("AI Error:"):
                self.fail(service.status)
            time.sleep(0.01)
        self.fail("Inference result was not produced.")

    def test_result_keeps_frame_identity_and_only_classifies_valid_crop(self) -> None:
        service, clients = self.make_service()
        try:
            frame = np.zeros((4, 4, 3), dtype=np.uint8)
            service.submit(frame, frame_id=23, timestamp_ms=766.67)

            result = self.wait_for_result(service)

            self.assertEqual(result.frame_id, 23)
            self.assertEqual(result.session_id, service.session_id)
            self.assertAlmostEqual(result.timestamp_ms, 766.67)
            self.assertEqual(len(result.detections), 1)
            detection = result.detections[0]
            self.assertEqual(detection.yolo_class_id, 11)
            self.assertEqual(detection.cnn_class_id, 17)
            self.assertEqual(detection.cnn_class_name, "No entry")
            self.assertEqual(len(clients["cnn"].requests[0]["tensors"]), 1)
            tensor = np.frombuffer(
                base64.b64decode(clients["cnn"].requests[0]["tensors"][0]),
                dtype=np.float32,
            )
            self.assertEqual(tensor.size, 30 * 30 * 3)
        finally:
            service.close()

    def test_reset_discards_in_flight_result_and_pending_frames_are_bounded(self) -> None:
        yolo_started = threading.Event()
        release_yolo = threading.Event()
        service, _clients = self.make_service(yolo_started, release_yolo)
        try:
            frame = np.zeros((4, 4, 3), dtype=np.uint8)
            service.submit(frame, frame_id=1, timestamp_ms=10.0)
            self.assertTrue(yolo_started.wait(timeout=5))

            service.submit(frame, frame_id=2, timestamp_ms=20.0)
            service.invalidate("seek")
            service.submit(frame, frame_id=9, timestamp_ms=90.0)
            self.assertLessEqual(service._requests.qsize(), 1)
            release_yolo.set()

            result = self.wait_for_result(service)

            self.assertEqual(result.frame_id, 9)
            self.assertEqual(result.generation, service.generation)
        finally:
            release_yolo.set()
            service.close()

    def test_playback_reset_events_invalidate_previous_results(self) -> None:
        service, _clients = self.make_service()
        try:
            for event in (
                PlaybackEventType.OPEN_NEW_VIDEO,
                PlaybackEventType.REPLAY,
                PlaybackEventType.SEEK,
                PlaybackEventType.STOP,
            ):
                previous_generation = service.generation
                service.invalidate(event)
                self.assertEqual(service.generation, previous_generation + 1)
                self.assertIsNone(service.poll_result())
        finally:
            service.close()

    def test_preloading_keeps_exact_request_through_startup_and_reset(self) -> None:
        cnn_loading = threading.Event()
        release_cnn = threading.Event()
        clients: dict[str, FakeWorker] = {}

        def worker_factory(kind: str, _arguments: list[str], _root: Path) -> FakeWorker:
            if kind == "cnn":
                cnn_loading.set()
                if not release_cnn.wait(timeout=5):
                    raise TimeoutError("Test did not release fake CNN.")
            worker = FakeWorker(kind)
            clients[kind] = worker
            return worker

        service = InferenceService(
            project_root=PROJECT_ROOT, worker_factory=worker_factory, preload_workers=True
        )
        try:
            self.assertTrue(cnn_loading.wait(timeout=5))
            self.assertEqual(service.status, "AI Loading: CNN")
            frame = np.zeros((4, 4, 3), dtype=np.uint8)
            service.submit(frame, 3, 100.0)
            service.invalidate("seek")
            service.submit(frame, 1358, 45266.667)
            self.assertFalse(clients["yolo"].requests)
            release_cnn.set()

            result = self.wait_for_result(service)
            self.assertEqual(result.frame_id, 1358)
            self.assertEqual(service.worker_status["cnn"]["state"], "ready")
            self.assertEqual(len(clients["yolo"].requests), 1)
        finally:
            release_cnn.set()
            service.close()

    def test_worker_startup_timeout_is_reported_instead_of_waiting_forever(self) -> None:
        with self.assertRaisesRegex(
            InferenceServiceError, "timed out waiting for READY"
        ):
            _JsonLineWorker(
                "test",
                [sys.executable, "-c", "import time; time.sleep(10)"],
                PROJECT_ROOT,
                startup_timeout=0.05,
                response_timeout=1.0,
            )

    def test_startup_error_is_visible_and_worker_is_marked_failed(self) -> None:
        def failing_factory(
            _kind: str, _arguments: list[str], _working_directory: Path
        ) -> FakeWorker:
            raise InferenceServiceError("worker startup failed")

        service = InferenceService(
            project_root=PROJECT_ROOT,
            worker_factory=failing_factory,
        )
        try:
            service.submit(np.zeros((4, 4, 3), dtype=np.uint8), 0, 0.0)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and not service.status.startswith(
                "AI Error:"
            ):
                time.sleep(0.01)

            self.assertTrue(service.status.startswith("AI Error:"))
            self.assertEqual(service.worker_status["yolo"]["state"], "error")
            self.assertEqual(
                service.worker_status["yolo"]["error"], "worker startup failed"
            )
            service.invalidate("replay")
            self.assertIn("worker startup failed", service.status)
        finally:
            service.close()

    def test_no_detection_is_reported_without_starting_cnn_worker(self) -> None:
        service, clients = self.make_service(no_detections=True)
        try:
            service.submit(np.zeros((4, 4, 3), dtype=np.uint8), 3, 100.0)

            result = self.wait_for_result(service)

            self.assertEqual(result.detections, ())
            self.assertNotIn("cnn", clients)
            self.assertEqual(service.diagnostics["last_yolo_detection_count"], 0)
            self.assertEqual(service.diagnostics["last_valid_crop_count"], 0)
            self.assertEqual(
                service.worker_status["yolo"]["state"],
                "ready",
            )
        finally:
            service.close()


class PausedFrameInferenceTests(unittest.TestCase):
    def test_pause_resubmits_the_exact_frame_currently_displayed(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        player._alerts = Mock()
        player._after_id = None
        player._displayed_frame_id = 15
        player._source_eof = False
        player.controller = Mock()
        player.controller.frame_count = 100
        player.controller.frame_index = 16
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        player.controller.seek.return_value = frame
        player._set_overlay_buffer_depth = Mock()
        player._queue_frame = Mock()
        player.status_var = Mock()
        player._refresh_controls = Mock()

        player.pause_video()

        player.controller.pause.assert_called_once_with()
        player.controller.seek.assert_called_once_with(15)
        player._queue_frame.assert_called_once_with(
            frame, 15, display_immediately=True
        )

    def test_late_result_can_overlay_only_its_exact_paused_frame(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        player.inference = Mock()
        player.inference.session_id = 7
        player.controller = Mock()
        player.controller.state = PlaybackState.PAUSED
        player._frame_buffer = deque()
        player._buffered_results = {}
        player._displayed_session_id = 7
        player._displayed_frame_id = 11
        player._displayed_timestamp_ms = 366.67
        player._current_display_frame = np.zeros((4, 4, 3), dtype=np.uint8)
        player._current_source_size = (4, 4)
        player.max_overlay_age_ms = 1500
        player._last_overlay_latency_ms = None
        player._overlay_status = None
        player._overlay_drop_log_times = {}
        player._overlay_rejection_counts = {}
        player._display_frame = Mock()
        player._update_ai_metrics = Mock()
        detection = ClassifiedDetection(
            bbox=(0.0, 0.0, 2.0, 2.0),
            yolo_class_id=1,
            yolo_class_name="traffic sign",
            yolo_confidence=0.9,
            cnn_class_id=17,
            cnn_class_name="No entry",
            cnn_score=0.9,
        )
        result = InferenceResult(
            session_id=7,
            frame_id=11,
            timestamp_ms=366.67,
            submitted_monotonic=time.perf_counter() - 10.0,
            completed_monotonic=time.perf_counter(),
            elapsed_ms=10000.0,
            detections=(detection,),
        )

        player._handle_inference_result(replace(result, frame_id=10))
        player._handle_inference_result(replace(result, session_id=6))
        player._display_frame.assert_not_called()
        player._handle_inference_result(result)

        player._display_frame.assert_called_once()
        self.assertEqual(player._overlay_status, "Detection Found")


class BufferedFrameInferenceTests(unittest.TestCase):
    def test_catchup_presents_the_exact_recent_positive_image(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        images = [
            DisplayFrame(7, i, i * 1000 / 30, 4, 4, np.full((4, 4, 3), i, dtype=np.uint8))
            for i in range(10, 15)
        ]
        detection = ClassifiedDetection((0.0, 0.0, 2.0, 2.0), 4, "Give Way", 0.9, 13, "Yield", 1.0)
        submitted = time.perf_counter() - 1.0
        result = InferenceResult(7, 12, images[2].timestamp_ms, submitted, submitted + 0.3, 300, (detection,))
        player._frame_buffer = deque(images)
        player._source_eof = False
        player._buffered_results = {12: result}
        player._clock_started = submitted
        player._clock_index = Mock(return_value=14)
        player.display_buffer_ms = 1200
        player.controller = Mock(fps=30.0)
        player._display_frame = Mock()
        player.max_overlay_age_ms = 1500

        player._display_next_buffered_frame()

        player._display_frame.assert_called_once_with(images[2], detections=(detection,))
        self.assertEqual([frame.frame_id for frame in player._frame_buffer], [13, 14])

    def test_result_that_finished_on_time_stays_with_its_buffered_frame(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        frame = DisplayFrame(7, 11, 366.67, 4, 4, np.zeros((4, 4, 3), dtype=np.uint8))
        detection = ClassifiedDetection((0.0, 0.0, 2.0, 2.0), 4, "Give Way", 0.9, 13, "Yield", 1.0)
        submitted = time.perf_counter() - 4.0
        result = InferenceResult(7, 11, 366.67, submitted, submitted + 0.3, 300, (detection,))
        player._frame_buffer = deque([frame])
        player._buffered_results = {11: result}
        player._buffer_delay_frames = 0
        player._source_eof = False
        player._display_frame = Mock()
        player.max_overlay_age_ms = 1500
        player._clock_started = time.perf_counter() - 1.2
        player._clock_frame = 11
        player._frame_interval = 1 / 30
        player.display_buffer_ms = 1200
        player.controller = Mock(fps=30.0)

        player._display_next_buffered_frame()

        player._display_frame.assert_called_once_with(frame, detections=(detection,))
        self.assertEqual(player._overlay_status, "Detection Found")

    def test_final_buffered_frame_completes_voice_session(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        frame = DisplayFrame(7, 11, 366.67, 4, 4, np.zeros((4, 4, 3), dtype=np.uint8))
        player._frame_buffer = deque([frame])
        player._source_eof = True
        player._buffered_results = {}
        player._clock_started = time.perf_counter()
        player._clock_index = Mock(return_value=11)
        player.display_buffer_ms = 1200
        player.controller = Mock(fps=30.0)
        player._display_frame = Mock()
        player._alerts = Mock()
        player._simulation = Mock()
        player.simulation_var = Mock()
        player.simulation_sign_var = Mock()
        player.simulation_event_type_var = Mock()
        player.simulation_action_var = Mock()
        player.simulation_image_label = Mock()
        player._refresh_controls = Mock()
        player.status_var = Mock()

        player._display_next_buffered_frame()

        player._display_frame.assert_called_once_with(frame, detections=())
        player._alerts.complete.assert_called_once_with()
        player._simulation.finish.assert_called_once_with()
        player.simulation_var.set.assert_called_once_with("Chưa có sự kiện mô phỏng")
        player.simulation_sign_var.set.assert_called_once_with("—")
        player.simulation_event_type_var.set.assert_called_once_with("—")
        player.simulation_action_var.set.assert_called_once_with("Chưa có sự kiện")
        player.status_var.set.assert_called_once_with("Video đã kết thúc")


@unittest.skipUnless(os.environ.get("TRAFFIC_SIGN_REAL_MODEL_TEST") == "1", "requires local models")
class RealModelRegressionTests(unittest.TestCase):
    def test_frame_1358_is_give_way_and_yield(self) -> None:
        reader = VideoReader(PROJECT_ROOT / "data" / "videos" / "test_video.mp4")
        reader.open()
        self.addCleanup(reader.close)
        frame, index = reader.seek(1358)
        self.assertEqual(index, 1358)
        service = InferenceService(project_root=PROJECT_ROOT, preload_workers=True)
        self.addCleanup(service.close)
        service.submit(frame, index, index / reader.fps * 1000)

        deadline = time.monotonic() + 250
        while time.monotonic() < deadline:
            self.assertFalse(service.status.startswith("AI Error:"), service.status)
            result = service.poll_result()
            if result is not None:
                self.assertEqual(result.frame_id, 1358)
                self.assertEqual(len(result.detections), 1)
                detection = result.detections[0]
                self.assertEqual((detection.yolo_class_name, detection.cnn_class_name), ("Give Way", "Yield"))
                self.assertIsNotNone(clip_bbox(detection.bbox, frame.shape[1], frame.shape[0]))
                return
            time.sleep(0.025)
        self.fail("Frame 1358 did not complete before the worker deadlines.")


if __name__ == "__main__":
    unittest.main()
