from __future__ import annotations

from collections import deque
import logging
import math
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from .inference_service import DEFAULT_DEMO_DETECTOR, InferenceService
from .playback_controller import PlaybackController, PlaybackEvent, PlaybackEventType, PlaybackState, PlaybackStateError
from .simulation_events import JsonlSimulationPublisher, SimulationEvent, SimulationSession
from .vision import (
    ClassifiedDetection,
    DisplayFrame,
    InferenceResult,
    draw_overlay,
    overlay_rejection_reason,
)
from .video_reader import VideoReaderError
from .sign_tracking import SignTracker
from .tracked_voice_alerts import TrackedVoiceAlerts

logger = logging.getLogger(__name__)
SIGN_IMAGE_DIRECTORY = Path(__file__).resolve().parents[2] / "assets" / "traffic_signs"


class FrameDisplayError(Exception):
    """Raised when a decoded frame cannot be displayed."""


class DesktopVideoPlayer:
    MAX_DISPLAY_SIZE = (960, 540)
    SIMULATION_SIGN_IMAGE_SIZE = (80, 80)
    DEBUG_METRIC_INTERVAL_SECONDS = 5.0
    CONTENT_COLUMN_WEIGHTS = (7, 3)
    UI_COLORS = {
        "window": "#F3F6FA",
        "surface": "#FFFFFF",
        "video": "#111827",
        "text": "#1F2937",
        "muted": "#64748B",
        "border": "#D8E1EC",
        "navy": "#17324D",
        "blue": "#2563EB",
        "blue_active": "#1D4ED8",
        "disabled": "#D6DEE8",
    }
    UI_FONT = "Segoe UI"

    def __init__(
        self,
        root: tk.Tk,
        controller: PlaybackController | None = None,
        image_size: int = 640,
        confidence: float = 0.25,
        max_overlay_age_ms: int = 2000,
        display_buffer_ms: int = 1800,
        ai_frame_interval_ms: int = 0,
        debug_seek: bool = False,
        detector: str = DEFAULT_DEMO_DETECTOR,
        alert_observations: int = 2,
        simulation_export_directory: Path | None = None,
    ) -> None:
        if not 0 <= max_overlay_age_ms <= 2000:
            raise ValueError("Maximum overlay age must be between 0 and 2000 ms.")
        if not 0 <= display_buffer_ms <= 2000:
            raise ValueError("Display buffer must be between 0 and 2000 ms.")
        if not 0 <= ai_frame_interval_ms <= 5000:
            raise ValueError("AI frame interval must be between 0 and 5000 ms.")
        if display_buffer_ms > max_overlay_age_ms:
            raise ValueError("Display buffer cannot exceed the maximum overlay age.")
        self.root = root
        self.controller = controller or PlaybackController()
        self.max_overlay_age_ms = max_overlay_age_ms
        self.display_buffer_ms = display_buffer_ms
        self.ai_frame_interval_ms = ai_frame_interval_ms
        self._last_ai_submit_at: float | None = None
        self._after_id: str | None = None
        self._next_frame_time = 0.0
        self._frame_interval = 0.0
        self._clock_started: float | None = None
        self._clock_frame = 0
        self._waiting_for_workers = False
        self._tracker = SignTracker()
        directory = simulation_export_directory or (
            Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TrafficSignDemo" / "simulation-events"
        )
        self._simulation_publisher = JsonlSimulationPublisher(directory)
        self._simulation = SimulationSession(self._simulation_publisher)
        self._alerts = TrackedVoiceAlerts(min_observations=alert_observations,
                                          on_confirmation=self._observe_simulation_event)
        self._pause_rewind = False
        self._photo: ImageTk.PhotoImage | None = None
        self._simulation_image_directory = SIGN_IMAGE_DIRECTORY
        self._simulation_image_cache: dict[int, ImageTk.PhotoImage | None] = {}
        self._active_simulation_image: ImageTk.PhotoImage | None = None
        self._updating_seekbar = False
        self._seeking_drag = False
        self._ai_poll_after_id: str | None = None
        self._frame_buffer: deque[DisplayFrame] = deque()
        self._buffered_results: dict[int, InferenceResult] = {}
        self._buffer_delay_frames = 0
        self._source_eof = False
        self._displayed_frame_id: int | None = None
        self._displayed_session_id: int | None = None
        self._displayed_timestamp_ms: float | None = None
        self._current_display_frame: np.ndarray | None = None
        self._current_source_size: tuple[int, int] | None = None
        self._display_times: deque[float] = deque(maxlen=120)
        self._overlay_status: str | None = None
        self._last_analysis_status: str | None = None
        self._last_overlay_latency_ms: float | None = None
        self._overlay_drop_log_times: dict[str, float] = {}
        self._overlay_rejection_counts: dict[str, int] = {}
        self._last_debug_metrics_at = 0.0
        self._reported_ai_error = False
        # Keep frame conversion and AI preprocessing from competing with the CPU workers.
        cv2.setNumThreads(1)
        self.inference = InferenceService(
            image_size=image_size, confidence=confidence, preload_workers=True,
            detector=detector,
        )
        self.controller.add_event_listener(self._handle_playback_event)

        root.title("Traffic Sign Video Demo 1.1")
        root.geometry("1320x720")
        root.minsize(960, 620)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.configure(background=self.UI_COLORS["window"])
        self._configure_styles(root)

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        content = ttk.Frame(root, style="App.TFrame", padding=16)
        content.grid(row=0, column=0, sticky="nsew")
        self.content_frame = content
        self._configure_content_columns(content)
        content.rowconfigure(0, weight=1)

        video_column = ttk.Frame(content, style="App.TFrame")
        video_column.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.video_column = video_column
        video_column.columnconfigure(0, weight=1)
        video_column.rowconfigure(0, weight=1)

        video_card = ttk.Frame(
            video_column, style="VideoCard.TFrame", padding=1
        )
        video_card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        video_card.columnconfigure(0, weight=1)
        video_card.rowconfigure(0, weight=1)
        self.video_card = video_card
        self.video_label = ttk.Label(
            video_card,
            anchor=tk.CENTER,
            text="Open an MP4 or AVI video",
            style="Video.TLabel",
            padding=8,
        )
        self.video_label.grid(row=0, column=0, sticky="nsew")

        events_panel = ttk.Frame(content, style="EventPanel.TFrame")
        events_panel.grid(row=0, column=1, sticky="new")
        events_panel.columnconfigure(0, weight=1)
        self.events_panel = events_panel

        self.events_heading = ttk.Label(
            events_panel,
            text="Simulation Events",
            style="EventHeader.TLabel",
        )
        self.events_heading.grid(row=0, column=0, sticky="ew")

        event_card = ttk.Frame(
            events_panel, style="EventCard.TFrame", padding=(18, 18)
        )
        event_card.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        event_card.columnconfigure(0, weight=1)
        self.event_card = event_card

        self.simulation_var = tk.StringVar(value="Chưa có sự kiện mô phỏng")
        self.simulation_sign_var = tk.StringVar(value="—")
        self.simulation_event_type_var = tk.StringVar(value="—")
        self.simulation_action_var = tk.StringVar(value="Chưa có sự kiện")

        ttk.Label(
            event_card, text="Biển báo", style="EventField.TLabel"
        ).grid(row=0, column=0, sticky="w")
        sign_row = ttk.Frame(event_card, style="EventContent.TFrame")
        sign_row.grid(row=1, column=0, sticky="ew", pady=(4, 16))
        sign_row.columnconfigure(1, weight=1)
        self.simulation_image_frame = ttk.Frame(
            sign_row,
            style="EventImage.TFrame",
            width=self.SIMULATION_SIGN_IMAGE_SIZE[0],
            height=self.SIMULATION_SIGN_IMAGE_SIZE[1],
        )
        self.simulation_image_frame.grid(
            row=0, column=0, sticky="nw", padx=(0, 12)
        )
        self.simulation_image_frame.grid_propagate(False)
        self.simulation_image_label = ttk.Label(
            self.simulation_image_frame,
            text="—",
            style="EventImage.TLabel",
            anchor=tk.CENTER,
        )
        self.simulation_image_label.grid(row=0, column=0, sticky="nsew")
        self.simulation_sign_label = ttk.Label(
            sign_row,
            textvariable=self.simulation_sign_var,
            style="EventSign.TLabel",
            wraplength=300,
            justify=tk.LEFT,
        )
        self.simulation_sign_label.grid(row=0, column=1, sticky="nw")

        ttk.Label(
            event_card, text="Event", style="EventField.TLabel"
        ).grid(row=2, column=0, sticky="w")
        self.simulation_event_type_label = ttk.Label(
            event_card,
            textvariable=self.simulation_event_type_var,
            style="EventType.TLabel",
            wraplength=300,
            justify=tk.LEFT,
        )
        self.simulation_event_type_label.grid(
            row=3, column=0, sticky="w", pady=(4, 14)
        )

        ttk.Separator(event_card, orient=tk.HORIZONTAL).grid(
            row=4, column=0, sticky="ew", pady=(0, 14)
        )
        ttk.Label(
            event_card, text="Đề xuất", style="EventField.TLabel"
        ).grid(row=5, column=0, sticky="w")
        self.simulation_action_label = ttk.Label(
            event_card,
            textvariable=self.simulation_action_var,
            style="EventAction.TLabel",
            wraplength=300,
            justify=tk.LEFT,
        )
        self.simulation_action_label.grid(
            row=6, column=0, sticky="w", pady=(4, 0)
        )
        self.simulation_label = self.simulation_sign_label
        events_panel.bind("<Configure>", self._resize_simulation_text)

        self.ai_status_var = tk.StringVar(value=self.inference.status)
        self.worker_status_var = tk.StringVar(value="YOLO: not started | CNN: not started")

        seek_controls = ttk.Frame(video_column, style="App.TFrame")
        seek_controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        self.seek_var = tk.DoubleVar(value=0)
        self.seek_bar = ttk.Scale(
            seek_controls,
            from_=0,
            to=0,
            orient=tk.HORIZONTAL,
            variable=self.seek_var,
            state=tk.DISABLED,
            style="Horizontal.TScale",
        )
        self.seek_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.seek_bar.bind("<ButtonPress-1>", self._begin_seek_drag)
        self.seek_bar.bind("<ButtonRelease-1>", self._seek_from_bar)

        self.time_var = tk.StringVar(value="00:00.000 / --:--")
        ttk.Label(
            seek_controls,
            textvariable=self.time_var,
            width=20,
            anchor=tk.E,
            style="Time.TLabel",
        ).pack(
            side=tk.RIGHT, padx=(14, 0)
        )
        self.seek_text = tk.StringVar()
        self.seek_button = ttk.Button(
            seek_controls, text="Go", width=5, command=self._seek_from_entry,
            state=tk.DISABLED, style="Secondary.TButton",
        )
        self.seek_entry = ttk.Entry(
            seek_controls, textvariable=self.seek_text, width=12, state=tk.DISABLED
        )
        self.seek_entry.bind("<Return>", self._seek_from_entry)
        self.debug_seek = debug_seek
        if debug_seek:
            self.seek_button.pack(side=tk.RIGHT, padx=(4, 0))
            self.seek_entry.pack(side=tk.RIGHT, padx=(8, 0))
            ttk.Label(seek_controls, text="Frame or mm:ss.sss").pack(side=tk.RIGHT, padx=(8, 0))

        controls = ttk.Frame(video_column, style="App.TFrame")
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        button_width = 11
        self.open_button = ttk.Button(
            controls,
            text="Open video",
            command=self.open_video,
            style="Primary.TButton",
            width=button_width,
        )
        self.open_button.pack(side=tk.LEFT, padx=(0, 8))

        self.pause_button = ttk.Button(
            controls, text="Pause", command=self.pause_video, state=tk.DISABLED,
            style="Secondary.TButton", width=button_width,
        )
        self.pause_button.pack(side=tk.LEFT, padx=(0, 8))

        self.resume_button = ttk.Button(
            controls, text="Resume", command=self.resume_video, state=tk.DISABLED,
            style="Secondary.TButton", width=button_width,
        )
        self.resume_button.pack(side=tk.LEFT, padx=(0, 8))

        self.replay_button = ttk.Button(
            controls, text="Replay", command=self.replay_video, state=tk.DISABLED,
            style="Secondary.TButton", width=button_width,
        )
        self.replay_button.pack(side=tk.LEFT, padx=(0, 8))

        self.stop_button = ttk.Button(
            controls, text="Stop", command=self.stop_video, state=tk.DISABLED,
            style="Secondary.TButton", width=button_width,
        )
        self.stop_button.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Sẵn sàng")
        self.status_label = ttk.Label(
            video_column,
            textvariable=self.status_var,
            anchor=tk.W,
            style="Status.TLabel",
        )
        self.status_label.grid(row=3, column=0, sticky="ew")
        self._schedule_ai_poll()

    @classmethod
    def _configure_styles(cls, root: tk.Tk) -> None:
        colors = cls.UI_COLORS
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=colors["window"])
        style.configure(
            "App.TFrame",
            background=colors["window"],
        )
        style.configure(
            "VideoCard.TFrame",
            background=colors["surface"],
            bordercolor=colors["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Video.TLabel",
            background=colors["video"],
            foreground="#CBD5E1",
            font=(cls.UI_FONT, 12),
        )
        style.configure(
            "EventPanel.TFrame",
            background=colors["window"],
        )
        style.configure(
            "EventHeader.TLabel",
            background=colors["navy"],
            foreground=colors["surface"],
            font=(cls.UI_FONT, 13, "bold"),
            padding=(16, 13),
        )
        style.configure(
            "EventCard.TFrame",
            background=colors["surface"],
            bordercolor=colors["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "EventContent.TFrame",
            background=colors["surface"],
        )
        style.configure(
            "EventImage.TFrame",
            background=colors["window"],
            bordercolor=colors["border"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "EventImage.TLabel",
            background=colors["window"],
            foreground=colors["muted"],
            font=(cls.UI_FONT, 16, "bold"),
        )
        style.configure(
            "EventField.TLabel",
            background=colors["surface"],
            foreground=colors["muted"],
            font=(cls.UI_FONT, 9, "bold"),
        )
        style.configure(
            "EventSign.TLabel",
            background=colors["surface"],
            foreground=colors["text"],
            font=(cls.UI_FONT, 16, "bold"),
        )
        style.configure(
            "EventType.TLabel",
            background=colors["surface"],
            foreground=colors["text"],
            font=(cls.UI_FONT, 11, "bold"),
        )
        style.configure(
            "EventAction.TLabel",
            background=colors["surface"],
            foreground=colors["text"],
            font=(cls.UI_FONT, 12),
        )
        style.configure(
            "Time.TLabel",
            background=colors["window"],
            foreground=colors["text"],
            font=(cls.UI_FONT, 10, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=colors["window"],
            foreground=colors["muted"],
            font=(cls.UI_FONT, 10),
        )
        style.configure(
            "Horizontal.TScale",
            background=colors["window"],
            troughcolor="#DCE4EF",
            sliderthickness=14,
            borderwidth=0,
        )
        style.configure(
            "Primary.TButton",
            background=colors["blue"],
            foreground=colors["surface"],
            borderwidth=0,
            padding=(12, 9),
            font=(cls.UI_FONT, 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("disabled", colors["disabled"]),
                ("active", colors["blue_active"]),
            ],
            foreground=[
                ("disabled", colors["muted"]),
                ("active", colors["surface"]),
            ],
        )
        style.configure(
            "Secondary.TButton",
            background=colors["surface"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            borderwidth=1,
            padding=(12, 9),
            font=(cls.UI_FONT, 10, "bold"),
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("disabled", "#EDF1F6"),
                ("active", "#E8EEF6"),
            ],
            foreground=[
                ("disabled", colors["muted"]),
                ("active", colors["text"]),
            ],
        )

    @classmethod
    def _configure_content_columns(cls, content: ttk.Frame) -> None:
        content.columnconfigure(
            0, weight=cls.CONTENT_COLUMN_WEIGHTS[0], uniform="main-content"
        )
        content.columnconfigure(
            1, weight=cls.CONTENT_COLUMN_WEIGHTS[1], uniform="main-content"
        )

    def _resize_simulation_text(self, event: tk.Event[tk.Misc]) -> None:
        self.simulation_sign_label.configure(
            wraplength=max(120, event.width - 128)
        )
        wraplength = max(160, event.width - 52)
        self.simulation_event_type_label.configure(wraplength=wraplength)
        self.simulation_action_label.configure(wraplength=wraplength)

    def open_video(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select a video",
            filetypes=(
                ("Supported videos", "*.mp4 *.avi"),
                ("MP4 video", "*.mp4"),
                ("AVI video", "*.avi"),
            ),
        )
        if not selected:
            return

        logger.info("Loading video %s.", Path(selected).name)
        self._cancel_scheduled_frame()
        self._clear_frame()
        try:
            frame = self.controller.start(Path(selected))
        except VideoReaderError as exc:
            logger.error(
                "Video loading failed for %s (%s).",
                Path(selected).name,
                type(exc).__name__,
            )
            self._invalidate_ai("invalid video selection")
            self._set_status(str(exc))
            messagebox.showerror("Cannot open video", str(exc), parent=self.root)
            return

        self._begin_playback(frame, f"Playing: {Path(selected).name}")

    def pause_video(self) -> None:
        self._cancel_scheduled_frame()
        self.controller.pause()
        self._alerts.suspend()
        if (
            self._displayed_frame_id is not None
            and self.controller.frame_count is not None
        ):
            try:
                self._pause_rewind = True
                try:
                    frame = self.controller.seek(self._displayed_frame_id)
                finally:
                    self._pause_rewind = False
            except (PlaybackStateError, VideoReaderError) as exc:
                logger.warning(
                    "Could not resubmit paused frame %s for AI inference: %s",
                    self._displayed_frame_id,
                    exc,
                )
                self._set_status(f"Paused. Could not analyze this frame: {exc}")
                return
            else:
                actual_index = self.controller.frame_index - 1
                self._source_eof = False
                self._set_overlay_buffer_depth()
                try:
                    self._queue_frame(
                        frame, actual_index, display_immediately=True
                    )
                except FrameDisplayError as exc:
                    self._set_status(str(exc))
                    messagebox.showerror(
                        "Display error", str(exc), parent=self.root
                    )
                    return
        self._set_status("Paused.")
        self._refresh_controls()

    def resume_video(self) -> None:
        self.controller.resume()
        self._invalidate_ai("resume", preserve_alerts=True)
        snapshot = self._current_snapshot()
        if snapshot is not None:
            self._display_frame(snapshot, count_for_fps=False)
        self._start_clock()
        self._waiting_for_workers = not self._workers_finished_loading()
        self._set_status(
            "Loading models. Playback will start automatically."
            if self._waiting_for_workers else "Playing."
        )
        self._refresh_controls()
        self._schedule_next_frame()

    def replay_video(self) -> None:
        self._cancel_scheduled_frame()
        try:
            frame = self.controller.replay()
        except (PlaybackStateError, VideoReaderError) as exc:
            self._set_status(str(exc))
            messagebox.showerror("Cannot replay video", str(exc), parent=self.root)
            return

        self._begin_playback(frame, "Playing from the beginning.")

    def _seek_from_bar(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self._updating_seekbar:
            return
        try:
            requested_index = int(round(self.seek_var.get()))
        except (tk.TclError, ValueError):
            self._seeking_drag = False
            return
        self._seek_to_frame(requested_index)

    def _seek_from_entry(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self.seek_entry.instate(("disabled",)):
            return
        try:
            requested_index = self._parse_seek_position(self.seek_text.get(), self.controller.fps)
        except (ValueError, OverflowError):
            self._set_status("Enter a zero-based frame number or a time such as 00:45.267.")
            return
        self._seek_to_frame(requested_index)

    def _seek_to_frame(self, requested_index: int) -> None:
        previous_state = self.controller.state
        if previous_state is PlaybackState.PLAYING:
            self._cancel_scheduled_frame()

        try:
            frame = self.controller.seek(requested_index)
        except (PlaybackStateError, VideoReaderError) as exc:
            self._seeking_drag = False
            self._set_status(str(exc))
            messagebox.showerror("Cannot seek video", str(exc), parent=self.root)
            if previous_state is PlaybackState.PLAYING:
                self._next_frame_time = time.perf_counter() + self._frame_interval
                self._schedule_next_frame()
            return

        self._seeking_drag = False
        actual_index = self.controller.frame_index - 1
        self.seek_var.set(actual_index)
        self._source_eof = False
        self._set_overlay_buffer_depth()
        try:
            self._queue_frame(frame, actual_index, display_immediately=True)
        except FrameDisplayError as exc:
            self.controller.stop()
            self._set_status(str(exc))
            messagebox.showerror("Display error", str(exc), parent=self.root)
            return
        if self.controller.state is PlaybackState.PLAYING:
            self._start_clock()
            self._waiting_for_workers = not self._workers_finished_loading()
            self._set_status(
                "Loading models. Playback will start automatically."
                if self._waiting_for_workers else "Playing from the selected position."
            )
            self._schedule_next_frame()
        else:
            self._set_status("Paused at the selected position.")
        if actual_index != requested_index:
            self._set_status(
                f"Decoder returned frame {actual_index} for requested frame {requested_index}."
            )
        self._refresh_controls()

    def stop_video(self) -> None:
        self._cancel_scheduled_frame()
        self.controller.stop()
        self._clear_frame()
        self._set_status("Stopped. Ready to open a video.")

    def close(self) -> None:
        self._cancel_scheduled_frame()
        if self._ai_poll_after_id is not None:
            self.root.after_cancel(self._ai_poll_after_id)
            self._ai_poll_after_id = None
        self.controller.stop()
        self._simulation_publisher.close()
        self._alerts.close()
        self.inference.close()
        self._close_after_export(time.monotonic() + 2)

    def _close_after_export(self, deadline: float) -> None:
        if self._simulation_publisher.done.is_set():
            self.root.destroy()
        elif time.monotonic() >= deadline:
            logger.warning("Simulation export did not drain before closing.")
            self.root.destroy()
        else:
            self.root.after(25, self._close_after_export, deadline)

    def _schedule_next_frame(self) -> None:
        is_playing = self.controller.state is PlaybackState.PLAYING
        draining = self._source_eof and bool(self._frame_buffer)
        if self._after_id is not None or self._waiting_for_workers or not (is_playing or draining):
            return
        delay = max(0.0, self._next_frame_time - time.perf_counter())
        delay_ms = max(1, round(delay * 1000))
        self._after_id = self.root.after(delay_ms, self._advance_frame)

    def _advance_frame(self) -> None:
        self._after_id = None
        if self.controller.state is not PlaybackState.PLAYING:
            if self._source_eof:
                self._display_next_buffered_frame()
                self._schedule_display_deadline()
                self._schedule_next_frame()
            return

        try:
            frame = self.controller.read_next(self._clock_index())
        except VideoReaderError as exc:
            self.controller.stop()
            self._set_status(str(exc))
            messagebox.showerror("Video read error", str(exc), parent=self.root)
            return
        except PlaybackStateError:
            self.controller.stop()
            self._set_status("Playback stopped because the session state was invalid.")
            raise

        if frame is None:
            self._source_eof = True
            self._set_status("Displaying the final buffered frames.")
            self._refresh_controls()
            self._display_next_buffered_frame()
            self._schedule_display_deadline()
            self._schedule_next_frame()
            return

        frame_id = max(0, self.controller.frame_index - 1)
        try:
            self._queue_frame(frame, frame_id)
        except FrameDisplayError as exc:
            self.controller.stop()
            self._set_status(str(exc))
            messagebox.showerror("Display error", str(exc), parent=self.root)
            return
        self._next_frame_time = self._clock_started + (
            self.controller.frame_index - self._clock_frame
        ) * self._frame_interval
        self._display_next_buffered_frame()
        self._schedule_next_frame()

    def _start_clock(self) -> None:
        self._clock_started = time.perf_counter()
        self._clock_frame = self.controller.frame_index - 1
        self._next_frame_time = self._clock_started + self._frame_interval

    def _clock_index(self, display_delay_ms: int = 0) -> int:
        elapsed = time.perf_counter() - self._clock_started - display_delay_ms / 1000
        return self._clock_frame + math.floor(elapsed / self._frame_interval)

    def _schedule_display_deadline(self) -> None:
        if self._frame_buffer:
            self._next_frame_time = (
                self._clock_started + self.display_buffer_ms / 1000
                + (self._frame_buffer[0].frame_id - self._clock_frame) * self._frame_interval
            )

    def _display_frame(
        self,
        snapshot: DisplayFrame,
        detections: tuple[ClassifiedDetection, ...] = (),
        count_for_fps: bool = True,
    ) -> None:
        try:
            overlays = (
                self._tracker.update(snapshot, detections)
                if self.controller.state is PlaybackState.PLAYING else detections
            )
            display_frame = (
                draw_overlay(
                    snapshot.image,
                    overlays,
                    snapshot.source_width,
                    snapshot.source_height,
                )
                if overlays
                else snapshot.image
            )
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb_frame)
            if self._photo is None or (self._photo.width(), self._photo.height()) != image.size:
                self._photo = ImageTk.PhotoImage(image=image, master=self.root)
                self.video_label.configure(image=self._photo, text="")
            else:
                self._photo.paste(image)
        except (cv2.error, tk.TclError, ValueError) as exc:
            raise FrameDisplayError("Could not display a decoded video frame.") from exc

        self._current_display_frame = snapshot.image
        self._current_source_size = (snapshot.source_width, snapshot.source_height)
        self._displayed_session_id = snapshot.session_id
        self._displayed_frame_id = snapshot.frame_id
        self._displayed_timestamp_ms = snapshot.timestamp_ms
        if (
            (self.controller.state is PlaybackState.PLAYING or (self._source_eof and self._frame_buffer))
            and snapshot.session_id == self.inference.session_id
        ):
            self._alerts.observe(snapshot, detections)
        if count_for_fps:
            self._display_times.append(time.perf_counter())
            self._update_position()

    @classmethod
    def _resize_for_display(cls, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        max_width, max_height = cls.MAX_DISPLAY_SIZE
        scale = min(max_width / width, max_height / height, 1.0)
        if scale >= 1.0:
            return frame

        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        return cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)

    def _clear_frame(self) -> None:
        self._photo = None
        self.video_label.configure(image="", text="Open an MP4 or AVI video")
        self._current_display_frame = None
        self._current_source_size = None
        self._displayed_frame_id = None
        self._displayed_session_id = None
        self._displayed_timestamp_ms = None

    def _current_snapshot(self) -> DisplayFrame | None:
        if (
            self._displayed_session_id is None
            or self._displayed_frame_id is None
            or self._displayed_timestamp_ms is None
            or self._current_display_frame is None
            or self._current_source_size is None
        ):
            return None
        return DisplayFrame(
            self._displayed_session_id,
            self._displayed_frame_id,
            self._displayed_timestamp_ms,
            *self._current_source_size,
            self._current_display_frame,
        )

    def _begin_playback(self, frame: np.ndarray, status: str) -> None:
        self._frame_interval = 1.0 / self.controller.fps
        self._start_clock()
        self._waiting_for_workers = not self._workers_finished_loading()
        self._source_eof = False
        self._set_overlay_buffer_depth()
        try:
            self._queue_frame(frame, frame_id=0, display_immediately=True)
        except FrameDisplayError as exc:
            self.controller.stop()
            self._set_status(str(exc))
            messagebox.showerror("Display error", str(exc), parent=self.root)
            return
        self._set_status(
            "Loading models. Playback will start automatically."
            if self._waiting_for_workers
            else status
        )
        self._refresh_controls()
        self._schedule_next_frame()

    def _set_overlay_buffer_depth(self) -> None:
        fps = self.controller.fps
        self._buffer_delay_frames = max(
            0, math.floor(self.display_buffer_ms * fps / 1000.0)
        )

    def _queue_frame(
        self,
        frame: np.ndarray,
        frame_id: int,
        display_immediately: bool = False,
    ) -> None:
        height, width = frame.shape[:2]
        timestamp_ms = frame_id / self.controller.fps * 1000.0
        try:
            display_image = self._resize_for_display(frame)
        except cv2.error as exc:
            raise FrameDisplayError("Could not resize a decoded video frame.") from exc
        snapshot = DisplayFrame(
            session_id=self.inference.session_id,
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            source_width=width,
            source_height=height,
            image=display_image,
        )
        now = time.perf_counter()
        if display_immediately:
            self._overlay_status = None
            self._display_frame(snapshot)
            self._last_ai_submit_at = now
            self.inference.submit(frame, frame_id, timestamp_ms, copy_frame=False)
            return

        capacity = self._buffer_delay_frames + 2
        if len(self._frame_buffer) >= capacity:
            dropped = self._frame_buffer.popleft()
            self._buffered_results.pop(dropped.frame_id, None)
            logger.debug(
                "Dropped buffered display frame %s because the bounded buffer was full.",
                dropped.frame_id,
            )
        self._frame_buffer.append(snapshot)
        if self._should_submit_ai_frame(now):
            # The decoder owns a new array for each frame and rendering leaves it untouched.
            self.inference.submit(frame, frame_id, timestamp_ms, copy_frame=False, max_queue_age_ms=250)

    def _display_next_buffered_frame(self) -> None:
        if not self._frame_buffer:
            if self._source_eof:
                self._complete_video()
            return
        if self._clock_started is None:
            return
        due_frame = self._clock_index(self.display_buffer_ms)
        if self._frame_buffer[0].frame_id > due_frame:
            return
        # Prefer an on-time positive up to 100 ms behind the clock.
        # Its own image is presented, and the next tick catches up normally.
        preferred = max(
            (
                frame.frame_id for frame in self._frame_buffer
                if 0 <= due_frame - frame.frame_id <= self.controller.fps * 0.1
                and (candidate := self._buffered_results.get(frame.frame_id)) is not None
                and candidate.detections
                and overlay_rejection_reason(
                    candidate, frame.session_id, frame.frame_id, frame.timestamp_ms,
                    candidate.completed_monotonic, self.max_overlay_age_ms,
                ) is None
            ),
            default=due_frame,
        )
        while len(self._frame_buffer) > 1 and self._frame_buffer[1].frame_id <= preferred:
            dropped = self._frame_buffer.popleft()
            self._buffered_results.pop(dropped.frame_id, None)

        self._overlay_status = None
        snapshot = self._frame_buffer.popleft()
        result = self._buffered_results.pop(snapshot.frame_id, None)
        detections: tuple[ClassifiedDetection, ...] = ()
        if result is not None:
            rejection = overlay_rejection_reason(
                result,
                snapshot.session_id,
                snapshot.frame_id,
                snapshot.timestamp_ms,
                # A matching result that finished on time stays with its buffered frame.
                result.completed_monotonic,
                self.max_overlay_age_ms,
            )
            if rejection is None:
                detections = result.detections
                self._last_overlay_latency_ms = (
                    time.perf_counter() - result.submitted_monotonic
                ) * 1000.0
                self._overlay_status = (
                    "Detection Found" if detections else "No Detection"
                )
            else:
                self._log_overlay_drop(result, rejection)
                if result.detections:
                    self._overlay_status = (
                        f"Detection Found | Overlay skipped ({rejection})"
                    )
        try:
            self._display_frame(snapshot, detections=detections)
        except FrameDisplayError as exc:
            self.controller.stop()
            self._set_status(str(exc))
            messagebox.showerror("Display error", str(exc), parent=self.root)
            return
        if self._source_eof and not self._frame_buffer:
            self._complete_video()

    def _complete_video(self) -> None:
        self._alerts.complete()
        self._clear_simulation_session()
        self._set_status("Video playback completed.")
        self._refresh_controls()

    def _handle_playback_event(self, event: object) -> None:
        self._invalidate_ai(event, preserve_alerts=self._pause_rewind)

    def _invalidate_ai(self, reason: object, *, preserve_alerts: bool = False) -> None:
        self.inference.invalidate(reason)
        self._tracker.reset()
        if not preserve_alerts:
            self._alerts.reset(getattr(getattr(reason, "event_type", None), "value", str(reason)))
        if preserve_alerts:
            self._simulation.rebind(self.inference.session_id)
        elif isinstance(reason, PlaybackEvent) and reason.event_type in {
            PlaybackEventType.OPEN_NEW_VIDEO, PlaybackEventType.REPLAY, PlaybackEventType.SEEK,
        }:
            self._simulation.begin(self.inference.session_id)
            self._clear_simulation_panel()
        else:
            self._clear_simulation_session()
        self._waiting_for_workers = False
        self._frame_buffer.clear()
        self._buffered_results.clear()
        self._source_eof = False
        self._overlay_status = None
        self._last_analysis_status = None
        self._last_overlay_latency_ms = None
        self._last_ai_submit_at = None
        self._display_times.clear()
        self._overlay_drop_log_times.clear()
        self._overlay_rejection_counts.clear()
        self._update_ai_metrics()

    def _observe_simulation_event(self, frame, track) -> None:
        event = self._simulation.observe(frame, track)
        if event is not None:
            logger.debug(
                "Confirmed simulation event id=%s type=%s class_id=%s track_id=%s.",
                event.event_id,
                event.event_type,
                event.class_id,
                event.track_id,
            )
            formatted = self._format_simulation_event(event)
            if formatted is not None:
                self.simulation_var.set(formatted)
                self.simulation_sign_var.set(event.class_name_vi)
                self.simulation_event_type_var.set(event.event_type)
                self.simulation_action_var.set(event.suggested_action)
                self._set_simulation_sign_image(event.class_id)

    @staticmethod
    def _format_simulation_event(event: SimulationEvent) -> str | None:
        if (
            not event.confirmed
            or event.decision_status != "confirmed"
            or not event.suggested_action
        ):
            return None
        return (
            f"Biển báo: {event.class_name_vi}\n\n"
            f"Event: {event.event_type}\n\n"
            f"Đề xuất: {event.suggested_action}"
        )

    def _set_simulation_sign_image(self, class_id: int | None) -> None:
        if class_id is None:
            photo = None
        elif class_id in self._simulation_image_cache:
            photo = self._simulation_image_cache[class_id]
        else:
            image_path = self._simulation_image_directory / f"{class_id}.png"
            try:
                with Image.open(image_path) as source:
                    image = source.convert("RGBA")
                image.thumbnail(
                    self.SIMULATION_SIGN_IMAGE_SIZE, Image.Resampling.LANCZOS
                )
                photo = ImageTk.PhotoImage(image, master=self.root)
            except (OSError, ValueError, tk.TclError) as exc:
                logger.warning(
                    "Unable to load simulation sign image %s: %s",
                    image_path.name,
                    exc,
                )
                photo = None
            self._simulation_image_cache[class_id] = photo

        self._active_simulation_image = photo
        self.simulation_image_label.configure(
            image=photo if photo is not None else "",
            text="" if photo is not None else "—",
        )
        self.simulation_image_label.image = photo

    def _clear_simulation_panel(self) -> None:
        self.simulation_var.set("Chưa có sự kiện mô phỏng")
        self.simulation_sign_var.set("—")
        self.simulation_event_type_var.set("—")
        self.simulation_action_var.set("Chưa có sự kiện")
        self._set_simulation_sign_image(None)

    def _clear_simulation_session(self) -> None:
        self._simulation.finish()
        self._clear_simulation_panel()

    def _should_submit_ai_frame(self, now: float) -> bool:
        interval = self.ai_frame_interval_ms / 1000.0
        if (
            self._last_ai_submit_at is not None
            and now - self._last_ai_submit_at < interval
        ):
            return False
        self._last_ai_submit_at = now
        return True

    def _schedule_ai_poll(self) -> None:
        if self._ai_poll_after_id is None:
            self._ai_poll_after_id = self.root.after(25, self._poll_ai_results)

    def _poll_ai_results(self) -> None:
        self._ai_poll_after_id = None
        if self._waiting_for_workers and self._workers_finished_loading():
            self._waiting_for_workers = False
            if self.inference.status.startswith("AI Error:"):
                if not self._reported_ai_error:
                    self._set_status("AI Error")
                    self._reported_ai_error = True
            elif self.controller.state is PlaybackState.PLAYING:
                self._reported_ai_error = False
                self._start_clock()
                self._set_status("Playing.")
                self._schedule_next_frame()
        result = self.inference.poll_result()
        if result is not None:
            try:
                self._handle_inference_result(result)
            except FrameDisplayError as exc:
                logger.exception("Could not render AI result for frame %s.", result.frame_id)
                self._set_status(str(exc))
        self._update_ai_metrics()
        if self.inference.status.startswith("AI Error:") and not self._reported_ai_error:
            self._set_status("AI Error")
            self._reported_ai_error = True
        elif not self.inference.status.startswith("AI Error:"):
            self._reported_ai_error = False
        self._log_debug_metrics()
        self._schedule_ai_poll()

    def _workers_finished_loading(self) -> bool:
        if self.inference.status.startswith("AI Error:"):
            return True
        return all(details["state"] == "ready" for details in self.inference.worker_status.values())

    def _handle_inference_result(self, result: InferenceResult) -> None:
        if result.session_id != self.inference.session_id:
            self._log_overlay_drop(
                result,
                f"old session (current session {self.inference.session_id})",
            )
            return

        outcome = "Detection Found" if result.detections else "No Detection"
        self._last_analysis_status = f"{outcome} (frame {result.frame_id})"
        buffered = next(
            (frame for frame in self._frame_buffer if frame.frame_id == result.frame_id),
            None,
        )
        snapshot = self._current_snapshot()
        if (
            snapshot is not None
            and snapshot.session_id == result.session_id
            and snapshot.frame_id == result.frame_id
        ):
            rejection = overlay_rejection_reason(
                result,
                snapshot.session_id,
                snapshot.frame_id,
                snapshot.timestamp_ms,
                time.perf_counter(),
                (
                    math.inf
                    if self.controller.state is PlaybackState.PAUSED
                    else self.max_overlay_age_ms
                ),
            )
            if rejection is None:
                if result.detections:
                    self._display_frame(
                        snapshot, detections=result.detections, count_for_fps=False
                    )
                    self._last_overlay_latency_ms = (
                        time.perf_counter() - result.submitted_monotonic
                    ) * 1000.0
                self._overlay_status = outcome
            elif result.detections:
                self._reject_overlay(result, rejection)
            return

        if buffered is not None:
            self._buffered_results[result.frame_id] = result
            return

        if result.detections:
            self._reject_overlay(result, "source frame is no longer buffered or displayed")
        elif self._displayed_frame_id is not None and result.frame_id < self._displayed_frame_id:
            self._log_overlay_drop(
                result, "no-detection result belongs to an already displayed frame"
            )

    def _reject_overlay(self, result: InferenceResult, reason: str) -> None:
        self._log_overlay_drop(result, reason)
        self._overlay_status = f"Detection Found | Overlay skipped ({reason})"

    def _log_overlay_drop(self, result: InferenceResult, reason: str) -> None:
        now = time.perf_counter()
        self._overlay_rejection_counts[reason] = (
            self._overlay_rejection_counts.get(reason, 0) + 1
        )
        if now - self._overlay_drop_log_times.get(reason, 0.0) >= 5.0:
            self._overlay_drop_log_times[reason] = now
            logger.debug(
                "Rejected AI result session=%s frame=%s: %s.",
                result.session_id,
                result.frame_id,
                reason,
            )

    def _display_fps(self) -> float:
        now = time.perf_counter()
        while self._display_times and now - self._display_times[0] > 5.0:
            self._display_times.popleft()
        if len(self._display_times) < 2:
            return 0.0
        elapsed = self._display_times[-1] - self._display_times[0]
        return (len(self._display_times) - 1) / elapsed if elapsed > 0 else 0.0

    def _update_ai_metrics(self) -> None:
        inference_status = self.inference.status
        outcome = self._overlay_status or self._last_analysis_status
        status = inference_status
        if outcome and not inference_status.startswith("AI Error:"):
            status = outcome
            if inference_status == "AI Processing":
                status = f"AI Processing | {outcome}"
        latency = self.inference.last_latency_ms
        latency_text = f"{latency:.0f} ms" if latency is not None else "--"
        overlay_latency = self._last_overlay_latency_ms
        overlay_latency_text = (
            f"{overlay_latency:.0f} ms" if overlay_latency is not None else "--"
        )
        ai_summary = (
            f"{status} | Display FPS: {self._display_fps():.1f} "
            f"| AI FPS: {self.inference.ai_fps:.1f} "
            f"| Inference: {latency_text} "
            f"| Overlay delay: {overlay_latency_text}"
        )
        if self.ai_status_var.get() != ai_summary:
            self.ai_status_var.set(ai_summary)
        worker_status = self.inference.worker_status
        worker_summaries = []
        for name in ("yolo", "cnn"):
            details = worker_status[name]
            state = str(details["state"]).title()
            startup_seconds = details.get("startup_seconds")
            started_at = details.get("started_monotonic")
            if state == "Starting" and isinstance(started_at, (int, float)):
                state = f"Loading ({time.perf_counter() - float(started_at):.0f}s)"
            elif state == "Ready" and isinstance(startup_seconds, (int, float)):
                state += f" ({float(startup_seconds):.1f}s)"
            error = details.get("error")
            if error:
                state += f": {error}"
            worker_summaries.append(f"{name.upper()}: {state}")
        diagnostics = self.inference.diagnostics
        source_frames = max(0, self.controller.frame_index - self._clock_frame)
        if source_frames and self.controller.state is PlaybackState.PLAYING:
            coverage = diagnostics["frames_analyzed"] / source_frames
            worker_summaries.append(f"Analyzed {coverage:.1%} of source frames")
        frame_id = diagnostics["last_frame_id"]
        detections = diagnostics["last_yolo_detection_count"]
        crops = diagnostics["last_valid_crop_count"]
        classifications = diagnostics["last_cnn_classification_count"]
        if frame_id is None:
            pipeline_summary = "No frame processed"
        else:
            timestamp_ms = diagnostics["last_timestamp_ms"]
            pipeline_summary = (
                f"Frame {frame_id} ({timestamp_ms / 1000:.3f}s): "
                f"YOLO detections {detections}, valid crops {crops if crops is not None else '--'}, "
                f"CNN labels {classifications if classifications is not None else '--'}"
            )
        rejected = sum(self._overlay_rejection_counts.values())
        pipeline_summary += f" | Overlay rejections: {rejected}"
        worker_summary = " | ".join(worker_summaries) + f" | {self._alerts.status} | {pipeline_summary}"
        if self.worker_status_var.get() != worker_summary:
            self.worker_status_var.set(worker_summary)

    @staticmethod
    def _user_status(message: str) -> str:
        normalized = message.casefold()
        if "ai error" in normalized or "worker failed" in normalized:
            return "Không thể khởi động hệ thống nhận diện. Vui lòng kiểm tra nhật ký lỗi."
        if "loading models" in normalized:
            return "Đang tải mô hình..."
        if "ready to open" in normalized or normalized == "sẵn sàng":
            return "Sẵn sàng"
        if "pause" in normalized:
            return "Đã tạm dừng"
        if "stop" in normalized or "stopped" in normalized:
            return "Đã dừng"
        if "completed" in normalized or "ended" in normalized:
            return "Video đã kết thúc"
        if "playing" in normalized:
            return "Đang phát video"
        if "detection found" in normalized or "ai processing" in normalized:
            return "Đang phân tích biển báo..."
        if "no detection" in normalized:
            return "Đang phát video"
        if "invalid" in normalized or "error" in normalized or "could not" in normalized:
            return "Không thể xử lý video. Vui lòng kiểm tra nhật ký lỗi."
        if "loading" in normalized:
            return "Đang tải..."
        return "Đang xử lý video..."

    def _set_status(self, message: str) -> None:
        self.status_var.set(self._user_status(message))
        self._refresh_controls()

    def _log_debug_metrics(self) -> None:
        now = time.perf_counter()
        if now - self._last_debug_metrics_at < self.DEBUG_METRIC_INTERVAL_SECONDS:
            return
        self._last_debug_metrics_at = now
        diagnostics = self.inference.diagnostics
        alert_diagnostics = self._alerts.diagnostics
        logger.debug(
            "Performance display_fps=%.2f ai_fps=%.2f inference_ms=%s "
            "overlay_ms=%s frames_analyzed=%s overlay_rejections=%s "
            "simulation_events_dropped=%s voice_generated=%s voice_played=%s voice_expired=%s.",
            self._display_fps(),
            self.inference.ai_fps,
            self.inference.last_latency_ms,
            self._last_overlay_latency_ms,
            diagnostics.get("frames_analyzed"),
            sum(self._overlay_rejection_counts.values()),
            self._simulation_publisher.dropped,
            alert_diagnostics.get("generated", 0),
            alert_diagnostics.get("played", 0),
            alert_diagnostics.get("expired", 0),
        )

    def _refresh_controls(self) -> None:
        state = self.controller.state
        has_video = self.controller.path is not None
        can_seek = (
            has_video
            and self.controller.frame_count is not None
            and state
            in {
                PlaybackState.PLAYING,
                PlaybackState.PAUSED,
                PlaybackState.COMPLETED,
            }
        )

        self.pause_button.configure(
            state=tk.NORMAL if state is PlaybackState.PLAYING else tk.DISABLED
        )
        self.resume_button.configure(
            state=tk.NORMAL if state is PlaybackState.PAUSED else tk.DISABLED
        )
        self.stop_button.configure(
            state=tk.NORMAL
            if has_video and state is not PlaybackState.STOPPED
            else tk.DISABLED
        )
        self.replay_button.configure(
            state=tk.NORMAL if has_video else tk.DISABLED
        )
        self.seek_bar.configure(
            to=max(0, (self.controller.frame_count or 1) - 1),
            state=tk.NORMAL if can_seek else tk.DISABLED,
        )
        seek_state = tk.NORMAL if can_seek else tk.DISABLED
        self.seek_button.configure(state=seek_state)
        self.seek_entry.configure(state=seek_state)
        self._update_position()

    def _update_position(self) -> None:
        state = self.controller.state
        has_video = self.controller.path is not None
        if not has_video:
            current_time = 0.0
            total_time = None
            seek_position = 0
        else:
            fps = self.controller.fps
            total_time = self.controller.duration
            if (
                state is PlaybackState.COMPLETED
                and self._source_eof
                and not self._frame_buffer
                and total_time is not None
            ):
                current_time = total_time
            elif state is PlaybackState.STOPPED:
                current_time = 0.0
            else:
                current_time = (
                    max(0, self._displayed_frame_id) / fps
                    if self._displayed_frame_id is not None
                    else 0.0
                )
            seek_position = (
                max(0, self._displayed_frame_id)
                if self._displayed_frame_id is not None
                else 0
            )

        if not self._seeking_drag:
            self._updating_seekbar = True
            try:
                self.seek_var.set(seek_position)
            finally:
                self._updating_seekbar = False
        minutes, millis = divmod(round(current_time * 1000), 60_000)
        seconds, millis = divmod(millis, 1000)
        current = f"{minutes:02d}:{seconds:02d}.{millis:03d}"
        total = self._format_time(total_time) if total_time is not None else "--:--"
        frame = f"   Frame {seek_position}" if self.debug_seek and self._displayed_frame_id is not None else ""
        self.time_var.set(f"{current} / {total}{frame}")

    @staticmethod
    def _parse_seek_position(text: str, fps: float) -> int:
        minutes, separator, seconds = text.strip().partition(":")
        if not separator:
            return int(minutes)
        minute_value = int(minutes)
        second_value = float(seconds)
        if minute_value < 0 or not 0 <= second_value < 60:
            raise ValueError("Invalid timestamp.")
        return round((minute_value * 60 + second_value) * fps)

    @staticmethod
    def _format_time(seconds: float) -> str:
        total_seconds = max(0, round(seconds))
        minutes, seconds_part = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds_part:02d}"

    def _begin_seek_drag(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        self._seeking_drag = True
        if self.controller.state is PlaybackState.PLAYING:
            self._cancel_scheduled_frame()

    def _cancel_scheduled_frame(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
