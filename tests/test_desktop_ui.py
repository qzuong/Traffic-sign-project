from collections import deque
from contextlib import ExitStack
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

from src.traffic_sign_demo import main as app_main
from src.traffic_sign_demo.class_mapping import load_class_mapping
from src.traffic_sign_demo.desktop_ui import SIGN_IMAGE_DIRECTORY, DesktopVideoPlayer
from src.traffic_sign_demo.playback_controller import PlaybackState


class DesktopVideoPlayerTests(unittest.TestCase):
    def test_launch_defaults_to_gtsdb_and_accepts_original_rollback(self) -> None:
        for args, detector in (([], "gtsdb"), (["--detector", "original"], "original")):
            with (
                self.subTest(args=args),
                patch.object(sys, "argv", ["traffic_sign_demo", *args]),
                patch.object(app_main.tk, "Tk") as create_root,
                patch.object(app_main, "DesktopVideoPlayer") as create_player,
                patch.object(app_main, "configure_logging") as configure_logging,
            ):
                app_main.main()
                configure_logging.assert_called_once_with(False)
                create_player.assert_called_once_with(
                    create_root.return_value, image_size=640, debug_seek=False, detector=detector
                )
                create_root.return_value.mainloop.assert_called_once_with()
                configure_logging.return_value.close.assert_called_once_with()

    def test_debug_flag_is_recognized_without_changing_other_cli_defaults(self) -> None:
        args = app_main._parse_args(["--debug"])

        self.assertTrue(args.debug)
        self.assertEqual(args.imgsz, 640)
        self.assertEqual(args.detector, "gtsdb")
        self.assertFalse(args.debug_seek)

    def test_debug_flag_enables_debug_terminal_logging(self) -> None:
        with (
            patch.object(app_main.tk, "Tk") as create_root,
            patch.object(app_main, "DesktopVideoPlayer"),
            patch.object(app_main, "configure_logging") as configure_logging,
        ):
            app_main.main(["--debug"])

        configure_logging.assert_called_once_with(True)
        configure_logging.return_value.close.assert_called_once_with()

    def test_ui_layout_places_events_beside_video_and_hides_diagnostics(self) -> None:
        class FakeVariable:
            def __init__(self, value=None):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        widgets = []

        def widget_factory(*args, **kwargs):
            widget = Mock()
            widget.parent = args[0] if args else None
            widget.options = kwargs
            widgets.append(widget)
            return widget

        root = Mock()
        controller = Mock()
        inference = Mock(status="AI Ready")
        inference.worker_status = {"yolo": {}, "cnn": {}}
        style = Mock()
        patches = (
            patch("src.traffic_sign_demo.desktop_ui.ttk.Frame", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.ttk.LabelFrame", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.ttk.Label", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.ttk.Scale", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.ttk.Separator", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.ttk.Button", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.ttk.Entry", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.tk.Scale", side_effect=widget_factory),
            patch("src.traffic_sign_demo.desktop_ui.ttk.Style", return_value=style),
            patch("src.traffic_sign_demo.desktop_ui.tk.StringVar", side_effect=FakeVariable),
            patch("src.traffic_sign_demo.desktop_ui.tk.DoubleVar", side_effect=FakeVariable),
            patch("src.traffic_sign_demo.desktop_ui.cv2.setNumThreads"),
            patch("src.traffic_sign_demo.desktop_ui.InferenceService", return_value=inference),
            patch("src.traffic_sign_demo.desktop_ui.JsonlSimulationPublisher"),
            patch("src.traffic_sign_demo.desktop_ui.SimulationSession"),
            patch("src.traffic_sign_demo.desktop_ui.TrackedVoiceAlerts"),
            patch("src.traffic_sign_demo.desktop_ui.SignTracker"),
            patch.object(DesktopVideoPlayer, "_schedule_ai_poll"),
        )
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            player = DesktopVideoPlayer(root, controller=controller)

        self.assertEqual(player.video_column.grid.call_args.kwargs["column"], 0)
        self.assertEqual(player.events_panel.grid.call_args.kwargs["column"], 1)
        self.assertEqual(player.events_panel.grid.call_args.kwargs["sticky"], "new")
        self.assertNotIn("pady", player.video_label.grid.call_args.kwargs)
        self.assertEqual(player.video_card.options["style"], "VideoCard.TFrame")
        self.assertEqual(player.events_heading.options["style"], "EventHeader.TLabel")
        self.assertEqual(player.open_button.options["style"], "Primary.TButton")
        self.assertEqual(player.pause_button.options["style"], "Secondary.TButton")
        self.assertEqual(player.seek_bar.options["style"], "Horizontal.TScale")
        self.assertEqual(player.simulation_sign_var.get(), "—")
        self.assertEqual(player.simulation_event_type_var.get(), "—")
        self.assertEqual(player.simulation_action_var.get(), "Chưa có sự kiện")
        self.assertEqual(player.simulation_image_label.options["text"], "—")
        self.assertEqual(
            (player.simulation_image_frame.options["width"],
             player.simulation_image_frame.options["height"]),
            DesktopVideoPlayer.SIMULATION_SIGN_IMAGE_SIZE,
        )
        style.theme_use.assert_called_once_with("clam")
        style.configure.assert_any_call(
            "EventHeader.TLabel",
            background=DesktopVideoPlayer.UI_COLORS["navy"],
            foreground=DesktopVideoPlayer.UI_COLORS["surface"],
            font=(DesktopVideoPlayer.UI_FONT, 13, "bold"),
            padding=(16, 13),
        )
        self.assertEqual(
            [item.kwargs["weight"] for item in player.content_frame.columnconfigure.call_args_list],
            [7, 3],
        )
        visible_variables = {
            widget.options["textvariable"]
            for widget in widgets
            if "textvariable" in widget.options
        }
        self.assertNotIn(player.ai_status_var, visible_variables)
        self.assertNotIn(player.worker_status_var, visible_variables)
        self.assertIn(player.status_var, visible_variables)
        self.assertNotIn(player.simulation_var, visible_variables)
        self.assertIn(player.simulation_sign_var, visible_variables)
        self.assertIn(player.simulation_event_type_var, visible_variables)
        self.assertIn(player.simulation_action_var, visible_variables)
        self.assertFalse(
            any("Simulator: Not Connected" in str(widget.options) for widget in widgets)
        )

    def test_sign_images_match_all_cnn_class_ids_load_at_80px_and_are_cached(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        mapping = load_class_mapping(project_root / "models" / "model.py")
        image_paths = {
            int(path.stem): path
            for path in SIGN_IMAGE_DIRECTORY.glob("*.png")
            if path.stem.isdigit()
        }

        self.assertEqual(set(mapping), set(range(43)))
        self.assertEqual(set(image_paths), set(mapping))
        self.assertEqual(mapping[0], "Speed limit (20km/h)")
        self.assertEqual(mapping[13], "Yield")
        self.assertEqual(mapping[14], "Stop")
        self.assertEqual(mapping[42], "End no passing veh > 3.5 tons")

        source_sizes = {}
        for class_id, path in image_paths.items():
            with Image.open(path) as image:
                source_sizes[class_id] = image.size

        player = object.__new__(DesktopVideoPlayer)
        player.root = Mock()
        player._simulation_image_directory = SIGN_IMAGE_DIRECTORY
        player._simulation_image_cache = {}
        player._active_simulation_image = None
        player.simulation_image_label = Mock()
        resized_images = []

        def create_photo(image, master):
            resized_images.append(image.copy())
            return object()

        image_open = Image.open
        with (
            patch(
                "src.traffic_sign_demo.desktop_ui.Image.open",
                wraps=image_open,
            ) as open_image,
            patch(
                "src.traffic_sign_demo.desktop_ui.ImageTk.PhotoImage",
                side_effect=create_photo,
            ) as photo_factory,
        ):
            for class_id in mapping:
                player._set_simulation_sign_image(class_id)
            for class_id in mapping:
                player._set_simulation_sign_image(class_id)

        self.assertEqual(open_image.call_count, 43)
        self.assertEqual(photo_factory.call_count, 43)
        self.assertEqual(set(player._simulation_image_cache), set(mapping))
        self.assertEqual(len(resized_images), 43)
        for class_id, image in zip(mapping, resized_images):
            with self.subTest(class_id=class_id):
                self.assertEqual(max(image.size), 80)
                self.assertAlmostEqual(
                    image.width / image.height,
                    source_sizes[class_id][0] / source_sizes[class_id][1],
                    delta=0.02,
                )

    def test_missing_or_invalid_sign_image_uses_neutral_placeholder(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        player.root = Mock()
        player._simulation_image_cache = {}
        player._active_simulation_image = None
        player.simulation_image_label = Mock()

        with TemporaryDirectory() as temporary_directory:
            player._simulation_image_directory = Path(temporary_directory)
            with self.assertLogs("src.traffic_sign_demo.desktop_ui", "WARNING"):
                player._set_simulation_sign_image(13)
            player.simulation_image_label.configure.assert_called_with(
                image="", text="—"
            )

            invalid_image = player._simulation_image_directory / "14.png"
            invalid_image.write_bytes(b"not a PNG image")
            with self.assertLogs("src.traffic_sign_demo.desktop_ui", "WARNING"):
                player._set_simulation_sign_image(14)
            player.simulation_image_label.configure.assert_called_with(
                image="", text="—"
            )

        self.assertIsNone(player._simulation_image_cache[13])
        self.assertIsNone(player._simulation_image_cache[14])

    def test_playback_status_is_short_and_vietnamese(self) -> None:
        self.assertEqual(DesktopVideoPlayer._user_status("Ready to open a video."), "Sẵn sàng")
        self.assertEqual(DesktopVideoPlayer._user_status("Paused."), "Đã tạm dừng")
        self.assertEqual(DesktopVideoPlayer._user_status("Playing."), "Đang phát video")
        self.assertEqual(
            DesktopVideoPlayer._user_status("AI Error: CNN worker failed"),
            "Không thể khởi động hệ thống nhận diện. Vui lòng kiểm tra nhật ký lỗi.",
        )

    def test_debug_logging_retains_performance_and_event_metrics(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        player._last_debug_metrics_at = 0.0
        player.inference = Mock(
            diagnostics={"frames_analyzed": 12},
            ai_fps=2.0,
            last_latency_ms=420.0,
        )
        player._last_overlay_latency_ms = 480.0
        player._overlay_rejection_counts = {"expired": 1}
        player._simulation_publisher = Mock(dropped=3)
        player._alerts = Mock(diagnostics={
            "generated": 2, "played": 1, "expired": 1
        })
        player._display_times = deque()

        with self.assertLogs("src.traffic_sign_demo.desktop_ui", "DEBUG") as records:
            player._log_debug_metrics()

        self.assertIn("display_fps=", records.output[0])
        self.assertIn("ai_fps=2.00", records.output[0])
        self.assertIn("inference_ms=420.0", records.output[0])
        self.assertIn("overlay_ms=480.0", records.output[0])
        self.assertIn("frames_analyzed=12", records.output[0])
        self.assertIn("simulation_events_dropped=3", records.output[0])

    def test_aspect_ratio_is_preserved_when_resizing(self) -> None:
        frame = np.zeros((721, 1280, 3), dtype=np.uint8)

        resized = DesktopVideoPlayer._resize_for_display(frame)

        self.assertAlmostEqual(
            resized.shape[1] / resized.shape[0],
            frame.shape[1] / frame.shape[0],
            delta=1 / resized.shape[0],
        )

    def test_open_video_displays_and_submits_first_frame_automatically(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        player._after_id = None
        player.controller = Mock(fps=30.0, frame_index=1, state=PlaybackState.PLAYING)
        player.controller.start.return_value = frame
        player.inference = Mock(session_id=7)
        player.inference.status = "AI Ready"
        player.inference.worker_status = {"yolo": {"state": "ready"}, "cnn": {"state": "ready"}}
        player.display_buffer_ms = 1200
        player._clear_frame = Mock()
        player._display_frame = Mock()
        player._refresh_controls = Mock()
        player._schedule_next_frame = Mock()
        player.status_var = Mock()

        with patch("src.traffic_sign_demo.desktop_ui.filedialog.askopenfilename", return_value="demo.mp4"):
            player.open_video()

        player.controller.start.assert_called_once_with(Path("demo.mp4"))
        snapshot = player._display_frame.call_args.args[0]
        self.assertEqual((snapshot.session_id, snapshot.frame_id, snapshot.timestamp_ms), (7, 0, 0))
        player.inference.submit.assert_called_once_with(frame, 0, 0, copy_frame=False)
        player._schedule_next_frame.assert_called_once_with()

    def test_format_time_rounds_to_nearest_second(self) -> None:
        self.assertEqual(DesktopVideoPlayer._format_time(12.4), "00:12")
        self.assertEqual(DesktopVideoPlayer._format_time(40.625), "00:41")
        self.assertEqual(DesktopVideoPlayer._format_time(59.6), "01:00")

    def test_exact_seek_accepts_frame_number_and_millisecond_timestamp(self) -> None:
        for position in ("1358", "00:45.267"):
            with self.subTest(position=position):
                self.assertEqual(DesktopVideoPlayer._parse_seek_position(position, 30), 1358)
        for position in ("00:60", "00:nan", "45.267"):
            with self.subTest(position=position), self.assertRaises(ValueError):
                DesktopVideoPlayer._parse_seek_position(position, 30)

    def test_resize_for_display_downscales_once_without_mutating_source(self) -> None:
        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
        original_shape = frame.shape

        resized = DesktopVideoPlayer._resize_for_display(frame)

        self.assertEqual(resized.shape, (540, 960, 3))
        self.assertEqual(frame.shape, original_shape)

    def test_resize_for_display_does_not_upscale_small_frames(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        resized = DesktopVideoPlayer._resize_for_display(frame)

        self.assertIs(resized, frame)

    def test_schedule_next_frame_does_not_create_duplicate_callbacks(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        player._after_id = None
        player._next_frame_time = 0.0
        player._source_eof = False
        player._waiting_for_workers = False
        player._frame_buffer = deque()
        player.root = Mock()
        player.root.after.return_value = "after#1"
        player.controller = Mock()
        player.controller.state = PlaybackState.PLAYING

        player._schedule_next_frame()
        player._schedule_next_frame()

        player.root.after.assert_called_once()
        self.assertEqual(player._after_id, "after#1")

    def test_model_startup_releases_playback_automatically(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        player._waiting_for_workers = True
        player._workers_finished_loading = Mock(side_effect=[False, True])
        player.controller = Mock(state=PlaybackState.PLAYING, path=Path("demo.mp4"))
        player.inference = Mock()
        player.inference.status = "AI Ready"
        player.inference.poll_result.return_value = None
        player._start_clock = Mock()
        player._schedule_next_frame = Mock()
        player._schedule_ai_poll = Mock()
        player._update_ai_metrics = Mock()
        player._log_debug_metrics = Mock()
        player._refresh_controls = Mock()
        player.status_var = Mock()
        player._reported_ai_error = False

        player._simulation_publisher = Mock(failures=0, dropped=0)
        player.simulation_status_var = Mock()
        player._poll_ai_results()
        player._schedule_next_frame.assert_not_called()
        player._poll_ai_results()
        player._schedule_next_frame.assert_called_once_with()
        player._start_clock.assert_called_once_with()
        self.assertFalse(player._waiting_for_workers)

    def test_ai_frame_submission_is_throttled_to_the_configured_interval(self) -> None:
        player = object.__new__(DesktopVideoPlayer)
        player.ai_frame_interval_ms = 500
        player._last_ai_submit_at = None

        self.assertTrue(player._should_submit_ai_frame(10.0))
        self.assertFalse(player._should_submit_ai_frame(10.25))
        self.assertTrue(player._should_submit_ai_frame(10.5))


if __name__ == "__main__":
    unittest.main()
