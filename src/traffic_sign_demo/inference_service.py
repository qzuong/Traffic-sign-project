from __future__ import annotations

import base64
from collections import deque
from dataclasses import dataclass
import json
import logging
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable

import cv2
import numpy as np

from .class_mapping import load_class_mapping
from .speech_evidence import speech_veto
from .vision import (
    ClassifiedDetection,
    InferenceResult,
    clip_bbox,
    preprocess_crop,
)

logger = logging.getLogger(__name__)
DEFAULT_DEMO_DETECTOR = "gtsdb"
DETECTOR_FILES = {
    "original": "traffic_sign_yolo.pt",
    "gtsdb": "candidates/gtsdb_yolov8n.pt",
}
GTSDB_SHA256 = "f1d5b008c38ea080aca89e82725fbf9080f70ea239378011df95b855f2e5797e"


class InferenceServiceError(Exception):
    """Raised when an isolated model worker cannot complete a request."""


@dataclass(frozen=True)
class _FrameRequest:
    session_id: int
    frame_id: int
    timestamp_ms: float
    submitted_monotonic: float
    frame: np.ndarray
    max_queue_age_ms: int | None = None

    @property
    def generation(self) -> int:
        return self.session_id


WorkerFactory = Callable[[str, list[str], Path], "_JsonLineWorker"]
WORKER_STARTUP_TIMEOUT_SECONDS = 120.0
WORKER_RESPONSE_TIMEOUT_SECONDS = 30.0
WORKER_PYTHON_PROBE_TIMEOUT_SECONDS = 8.0
WORKER_PYTHON_FLAGS = ("-E", "-X", "utf8")
WORKER_MODULES = {
    "yolo": ("numpy", "cv2", "torch", "ultralytics"),
    "cnn": ("numpy", "tensorflow"),
}
_PYTHON_PROBE = (
    "import importlib.util, json, sys; "
    "print(json.dumps([m for m in sys.argv[1:] if importlib.util.find_spec(m) is None]))"
)


class _JsonLineWorker:
    def __init__(
        self,
        worker_name: str,
        command: list[str],
        working_directory: Path,
        startup_timeout: float,
        response_timeout: float,
        environment: dict[str, str] | None = None,
        on_started: Callable[[subprocess.Popen[str]], None] | None = None,
    ) -> None:
        self.worker_name = worker_name
        self.command = tuple(command)
        self.python_path = command[0]
        self.startup_timeout = startup_timeout
        self.response_timeout = response_timeout
        self.started_monotonic = time.perf_counter()
        self.ready_monotonic: float | None = None
        self.ready_message: dict[str, object] = {}
        self._messages: queue.Queue[tuple[str | None, str | None]] = queue.Queue(
            maxsize=8
        )
        try:
            self._process = subprocess.Popen(
                command,
                cwd=working_directory,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=environment,
            )
        except OSError as exc:
            raise InferenceServiceError(
                f"Could not start model worker {command[0]}: {exc}"
            ) from exc
        if on_started is not None:
            try:
                on_started(self._process)
            except Exception:
                self.terminate()
                raise

        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            name=f"{worker_name}-stdout-reader",
            daemon=True,
        )
        self._reader_thread.start()
        try:
            ready = self._read_message(startup_timeout, "READY")
        except InferenceServiceError:
            self.terminate()
            raise
        if ready.get("type") != "ready":
            self.terminate()
            raise InferenceServiceError(
                f"{worker_name.upper()} worker did not become ready: "
                f"{ready.get('error', 'invalid READY message')}"
            )
        self.ready_message = ready
        self.ready_monotonic = time.perf_counter()

    def request(self, payload: dict[str, object]) -> dict[str, object]:
        if self._process.poll() is not None:
            raise InferenceServiceError(
                f"Model worker exited with code {self._process.returncode}."
            )
        stdin = self._process.stdin
        if stdin is None:
            raise InferenceServiceError("Model worker input is unavailable.")
        try:
            stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise InferenceServiceError("Could not send a request to the model worker.") from exc

        response = self._read_message(self.response_timeout, "inference result")
        if response.get("type") == "error":
            raise InferenceServiceError(str(response.get("error", "Model inference failed.")))
        if response.get("type") != "result":
            raise InferenceServiceError("Model worker returned an unexpected response.")
        return response

    def _read_stdout(self) -> None:
        stdout = self._process.stdout
        if stdout is None:
            self._enqueue_message((None, "stdout is unavailable"))
            return
        try:
            for line in stdout:
                self._enqueue_message((line, None))
        except (OSError, ValueError) as exc:
            self._enqueue_message((None, f"stdout read failed: {exc}"))
        else:
            self._enqueue_message((None, "closed stdout"))

    def _enqueue_message(self, message: tuple[str | None, str | None]) -> None:
        while True:
            try:
                self._messages.put(message, timeout=0.1)
                return
            except queue.Full:
                if self._process.poll() is not None:
                    return

    def _read_message(self, timeout: float, phase: str) -> dict[str, object]:
        try:
            line, reader_error = self._messages.get(timeout=timeout)
        except queue.Empty as exc:
            self.terminate()
            elapsed = time.perf_counter() - self.started_monotonic
            raise InferenceServiceError(
                f"{self.worker_name.upper()} worker timed out waiting for {phase} "
                f"after {elapsed:.1f}s (limit {timeout:.1f}s)."
            ) from exc
        if line is None:
            returncode = self._process.poll()
            raise InferenceServiceError(
                f"{self.worker_name.upper()} worker {reader_error}; "
                f"process exit code: {returncode}."
            )
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InferenceServiceError(
                f"{self.worker_name.upper()} worker returned invalid JSON."
            ) from exc
        if not isinstance(response, dict):
            raise InferenceServiceError(
                f"{self.worker_name.upper()} worker returned a non-object response."
            )
        return response

    def terminate(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=0.25)
        for stream in (self._process.stdin, self._process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
        reader_thread = getattr(self, "_reader_thread", None)
        if reader_thread is not None and reader_thread is not threading.current_thread():
            reader_thread.join(timeout=0.25)

    @property
    def pid(self) -> int:
        return self._process.pid


class InferenceService:
    def __init__(
        self,
        project_root: str | Path | None = None,
        image_size: int = 320,
        confidence: float = 0.25,
        worker_factory: WorkerFactory | None = None,
        preload_workers: bool = False,
        detector: str = "original",
    ) -> None:
        if image_size <= 0:
            raise ValueError("YOLO image size must be positive.")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("YOLO confidence must be between 0 and 1.")
        if detector not in DETECTOR_FILES:
            raise ValueError(f"Unknown YOLO detector: {detector}")

        self.project_root = (
            Path(project_root)
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.image_size = image_size
        self.confidence = confidence
        self.detector = detector
        self.yolo_model_path = self.project_root / "models" / DETECTOR_FILES[detector]
        self.cnn_model_path = self.project_root / "models" / "model.h5"
        self.mapping_path = self.project_root / "models" / "model.py"
        self._mapping = load_class_mapping(self.mapping_path)
        self._worker_factory = worker_factory or self._start_worker

        self._requests: queue.Queue[_FrameRequest] = queue.Queue(maxsize=1)
        self._results: queue.Queue[InferenceResult] = queue.Queue(maxsize=1)
        self._state_lock = threading.Lock()
        self._clients_lock = threading.Lock()
        self._clients: dict[str, _JsonLineWorker] = {}
        self._processes: list[subprocess.Popen[str]] = []
        self._temporary_directories: list[tempfile.TemporaryDirectory[str]] = []
        self._worker_status: dict[str, dict[str, object]] = {
            worker_name: {
                "state": "not started",
                "python": None,
                "pid": None,
                "startup_seconds": None,
                "error": None,
            }
            for worker_name in ("yolo", "cnn")
        }
        self._diagnostics: dict[str, object] = {
            "frames_submitted": 0,
            "yolo_inferences": 0,
            "last_session_id": None,
            "last_frame_id": None,
            "last_timestamp_ms": None,
            "last_yolo_detection_count": None,
            "last_valid_crop_count": None,
            "last_cnn_classification_count": None,
            "stale_results": 0,
            "result_queue_replacements": 0,
            "frames_analyzed": 0,
            "expired_requests": 0,
        }
        self._last_pipeline_log_at = 0.0
        self._generation = 0
        self._active_generation: int | None = None
        self._status = "AI Ready: waiting for a video"
        self._fatal_error: str | None = None
        self._completion_times: deque[float] = deque(maxlen=100)
        self._last_latency_ms: float | None = None
        self._closed = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            args=(preload_workers,),
            name="traffic-sign-inference",
            daemon=True,
        )
        self._thread.start()

    @property
    def generation(self) -> int:
        with self._state_lock:
            return self._generation

    @property
    def session_id(self) -> int:
        return self.generation

    @property
    def status(self) -> str:
        with self._state_lock:
            if self._status.startswith("AI Error:"):
                return self._status
            for name, details in self._worker_status.items():
                if details["state"] == "starting":
                    return f"AI Loading: {name.upper()}"
            if self._active_generation == self._generation or not self._requests.empty():
                return "AI Processing"
            return self._status

    @property
    def worker_status(self) -> dict[str, dict[str, object]]:
        with self._state_lock:
            return {
                name: dict(details) for name, details in self._worker_status.items()
            }

    @property
    def diagnostics(self) -> dict[str, object]:
        with self._state_lock:
            return dict(self._diagnostics)

    @property
    def ai_fps(self) -> float:
        now = time.perf_counter()
        with self._state_lock:
            while self._completion_times and now - self._completion_times[0] > 5.0:
                self._completion_times.popleft()
            if len(self._completion_times) < 2:
                return 0.0
            elapsed = self._completion_times[-1] - self._completion_times[0]
            return (len(self._completion_times) - 1) / elapsed if elapsed > 0 else 0.0

    @property
    def last_latency_ms(self) -> float | None:
        with self._state_lock:
            return self._last_latency_ms

    def invalidate(self, _reason: object = None) -> None:
        with self._state_lock:
            self._generation += 1
            if not self._status.startswith("AI Error:"):
                self._status = "AI Ready"
            self._completion_times.clear()
            self._last_latency_ms = None
            self._diagnostics.update(
                frames_analyzed=0,
                last_session_id=None,
                last_frame_id=None,
                last_timestamp_ms=None,
                last_yolo_detection_count=None,
                last_valid_crop_count=None,
                last_cnn_classification_count=None,
            )
            self._drain(self._requests)
            self._drain(self._results)

    def submit(
        self, frame: np.ndarray, frame_id: int, timestamp_ms: float,
        *, copy_frame: bool = True, max_queue_age_ms: int | None = None,
    ) -> None:
        if self._closed.is_set():
            return
        if frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0:
            raise ValueError("A non-empty BGR video frame is required.")
        if not math.isfinite(timestamp_ms) or timestamp_ms < 0:
            raise ValueError("Frame timestamp must be finite and non-negative.")
        with self._state_lock:
            if self._fatal_error is not None or self._closed.is_set():
                return
            self._diagnostics["frames_submitted"] = (
                int(self._diagnostics["frames_submitted"]) + 1
            )
            self._replace_latest(
                self._requests,
                _FrameRequest(
                    self._generation, frame_id, timestamp_ms, time.perf_counter(),
                    frame.copy() if copy_frame else frame, max_queue_age_ms,
                ),
            )

    def poll_result(self) -> InferenceResult | None:
        latest: InferenceResult | None = None
        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                break
            if result.session_id == self.session_id:
                latest = result
        return latest

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        with self._state_lock:
            self._generation += 1
            self._status = "AI Error: inference service closed."
        self._drain(self._requests)
        self._drain(self._results)
        with self._clients_lock:
            clients = tuple(self._clients.values())
            processes = tuple(self._processes)
            temporary_directories = tuple(self._temporary_directories)
        for client in clients:
            client.terminate()
        for process in processes:
            self._terminate_process(process)
        self._thread.join(timeout=1.0)
        for directory in temporary_directories:
            directory.cleanup()

    def _start_worker(
        self, worker_name: str, arguments: list[str], working_directory: Path
    ) -> _JsonLineWorker:
        python = self._python_for_worker(worker_name)
        if self._closed.is_set():
            raise InferenceServiceError("Inference service is closing.")
        with self._state_lock:
            self._worker_status[worker_name]["python"] = python
        command = [
            python,
            *WORKER_PYTHON_FLAGS,
            "-m",
            f"src.traffic_sign_demo.{worker_name}_worker",
            *arguments,
        ]
        environment = None
        if worker_name == "yolo":
            with self._clients_lock:
                if self._closed.is_set():
                    raise InferenceServiceError("Inference service is closing.")
                config_directory = tempfile.TemporaryDirectory(
                    prefix="traffic-sign-demo-yolo-"
                )
                self._temporary_directories.append(config_directory)
            environment = os.environ.copy()
            environment["YOLO_CONFIG_DIR"] = config_directory.name
        try:
            return _JsonLineWorker(
                worker_name,
                command,
                working_directory,
                startup_timeout=WORKER_STARTUP_TIMEOUT_SECONDS,
                response_timeout=WORKER_RESPONSE_TIMEOUT_SECONDS,
                environment=environment,
                on_started=lambda process: self._register_process(worker_name, process),
            )
        except InferenceServiceError as exc:
            override = f"TRAFFIC_SIGN_{worker_name.upper()}_PYTHON"
            raise InferenceServiceError(
                f"{exc} Python: {python}. Check this environment or set {override} "
                "to the full path of a working interpreter."
            ) from exc

    def _python_for_worker(self, worker_name: str) -> str:
        override_name = f"TRAFFIC_SIGN_{worker_name.upper()}_PYTHON"
        override = os.environ.get(override_name)
        modules = WORKER_MODULES[worker_name]
        if override is not None:
            candidates = [Path(os.path.expandvars(override)).expanduser()]
        else:
            candidates = self._worker_python_candidates(worker_name)

        issues = []
        for path in dict.fromkeys(candidates):
            if not path.is_absolute():
                path = self.project_root / path
            issue = self._probe_worker_python(path, modules)
            if issue is None:
                return str(path)
            issues.append(f"{path} ({issue})")

        checked = "; ".join(issues)
        raise InferenceServiceError(
            f"No compatible {worker_name.upper()} Python. Set {override_name} to the full "
            f"path of a Python with {', '.join(modules)}. Checked: {checked}"
        )

    def _worker_python_candidates(self, worker_name: str) -> list[Path]:
        executable = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
        candidates = [self.project_root / f".venv-{worker_name}" / executable]
        if worker_name == "yolo":
            sibling = self.project_root.parent / (self.project_root.name + ".venv-yolo")
            return candidates + [sibling / executable]

        if os.name == "nt":
            program_files = Path(
                os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles", r"C:\Program Files")
            )
            candidates.append(program_files / "Python313" / "python.exe")
        for interpreter in (getattr(sys, "_base_executable", None), sys.executable):
            if interpreter:
                candidates.append(Path(interpreter))
        return candidates

    def _probe_worker_python(self, path: Path, modules: tuple[str, ...]) -> str | None:
        if not path.is_file():
            return "interpreter not found"
        try:
            probe = subprocess.run(
                [str(path), *WORKER_PYTHON_FLAGS, "-c", _PYTHON_PROBE, *modules],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=WORKER_PYTHON_PROBE_TIMEOUT_SECONDS,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=True,
            )
            missing = json.loads(probe.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return f"dependency check failed: {exc}"
        return f"missing {', '.join(missing)}" if missing else None

    def _register_process(
        self, worker_name: str, process: subprocess.Popen[str]
    ) -> None:
        with self._clients_lock:
            if self._closed.is_set():
                self._terminate_process(process)
                raise InferenceServiceError("Inference service is closing.")
            self._processes.append(process)
        with self._state_lock:
            status = self._worker_status[worker_name]
            status["pid"] = process.pid

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                if process.poll() is None:
                    raise
                return
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.25)

    def _get_client(self, worker_name: str) -> _JsonLineWorker:
        with self._clients_lock:
            client = self._clients.get(worker_name)
        if client is not None:
            return client

        started_monotonic = time.perf_counter()
        with self._state_lock:
            self._worker_status[worker_name].update(
                state="starting",
                python=None,
                pid=None,
                started_monotonic=started_monotonic,
                startup_seconds=None,
                error=None,
            )

        if worker_name == "yolo":
            arguments = [
                "--model",
                str(self.yolo_model_path),
                "--imgsz",
                str(self.image_size),
                "--conf",
                str(self.confidence),
            ]
            if self.detector == "gtsdb":
                arguments.extend(("--verified-sha256", GTSDB_SHA256))
        else:
            arguments = [
                "--model",
                str(self.cnn_model_path),
                "--mapping",
                str(self.mapping_path),
            ]
        try:
            client = self._worker_factory(worker_name, arguments, self.project_root)
        except Exception as exc:
            self._set_worker_error(worker_name, str(exc))
            raise
        with self._clients_lock:
            if self._closed.is_set():
                client.terminate()
                raise InferenceServiceError("Inference service is closing.")
            existing = self._clients.setdefault(worker_name, client)
        if existing is not client:
            client.terminate()
        else:
            started_at = getattr(client, "started_monotonic", started_monotonic)
            ready_at = getattr(client, "ready_monotonic", time.perf_counter())
            startup_seconds = max(0.0, float(ready_at) - float(started_at))
            ready_message = getattr(client, "ready_message", {})
            with self._state_lock:
                status = self._worker_status[worker_name]
                status.update(
                    state="ready",
                    python=ready_message.get("python", status["python"]),
                    pid=getattr(client, "pid", status.get("pid")),
                    startup_seconds=startup_seconds,
                    ready_message=ready_message,
                    error=None,
                )
                if not self._closed.is_set():
                    self._status = "AI Ready"
            logger.info(
                "%s worker READY pid=%s startup=%.2fs",
                worker_name.upper(),
                self._worker_status[worker_name]["pid"],
                startup_seconds,
            )
            logger.debug(
                "%s worker interpreter: %s",
                worker_name.upper(),
                self._worker_status[worker_name]["python"],
            )
        return existing

    def _run(self, preload_workers: bool) -> None:
        try:
            if preload_workers:
                for worker_name in ("yolo", "cnn"):
                    if self._closed.is_set():
                        return
                    self._get_client(worker_name)

            while not self._closed.is_set():
                try:
                    request = self._requests.get(timeout=0.1)
                except queue.Empty:
                    continue
                with self._state_lock:
                    if request.generation != self._generation:
                        continue
                    if (
                        request.max_queue_age_ms is not None
                        and (time.perf_counter() - request.submitted_monotonic) * 1000
                        > request.max_queue_age_ms
                    ):
                        self._diagnostics["expired_requests"] += 1
                        continue
                    self._active_generation = request.generation
                result = self._infer(request)
                with self._state_lock:
                    self._active_generation = None
                    if result is None or result.generation != self._generation:
                        self._diagnostics["stale_results"] = (
                            int(self._diagnostics["stale_results"]) + 1
                        )
                        continue
                    self._completion_times.append(result.completed_monotonic)
                    self._diagnostics["frames_analyzed"] += 1
                    self._last_latency_ms = result.elapsed_ms
                    if self._results.full():
                        self._diagnostics["result_queue_replacements"] = (
                            int(self._diagnostics["result_queue_replacements"]) + 1
                        )
                    self._replace_latest(self._results, result)
                    self._status = "Detection Found" if result.detections else "No Detection"
        except Exception as exc:
            if self._closed.is_set():
                return
            with self._state_lock:
                self._active_generation = None
                self._fatal_error = str(exc)
                if not self._status.startswith("AI Error:"):
                    self._status = f"AI Error: {exc}"
                self._drain(self._requests)
            logger.exception("AI inference failed.")

    def _infer(self, request: _FrameRequest) -> InferenceResult | None:
        yolo_client = self._get_client("yolo")
        if self._is_stale(request.generation):
            return None
        inference_started = time.perf_counter()
        cnn_startup_seconds = 0.0
        success, encoded_frame = cv2.imencode(
            ".jpg", request.frame, [cv2.IMWRITE_JPEG_QUALITY, 90]
        )
        if not success:
            raise InferenceServiceError("Could not encode the video frame for YOLO.")
        yolo_started = time.perf_counter()
        stage_ms = {
            "queue": (inference_started - request.submitted_monotonic) * 1000,
            "jpeg_encode": (yolo_started - inference_started) * 1000,
        }

        try:
            yolo_response = yolo_client.request(
                {
                    "session_id": request.session_id,
                    "frame_id": request.frame_id,
                    "timestamp_ms": request.timestamp_ms,
                    "frame_jpeg": base64.b64encode(encoded_frame).decode("ascii"),
                }
            )
        except Exception as exc:
            self._set_worker_error("yolo", str(exc))
            raise
        self._validate_frame_identity(yolo_response, request)
        stage_ms["yolo_predict"] = float(yolo_response.get("predict_ms", 0))
        stage_ms["jpeg_decode"] = float(yolo_response.get("decode_ms", 0))
        stage_ms["yolo_ipc"] = max(
            0, (time.perf_counter() - yolo_started) * 1000
            - stage_ms["yolo_predict"] - stage_ms["jpeg_decode"],
        )
        height, width = request.frame.shape[:2]
        pending: list[tuple[tuple[float, float, float, float], int, str, float, np.ndarray, float]] = []
        raw_detections = yolo_response.get("detections")
        if not isinstance(raw_detections, list):
            raise InferenceServiceError("YOLO worker returned an invalid detection list.")
        with self._state_lock:
            self._diagnostics["yolo_inferences"] = int(self._diagnostics["yolo_inferences"]) + 1
            if request.generation != self._generation:
                return None
            self._diagnostics.update(
                last_session_id=request.session_id,
                last_frame_id=request.frame_id,
                last_timestamp_ms=request.timestamp_ms,
                last_yolo_detection_count=len(raw_detections),
                last_valid_crop_count=None,
                last_cnn_classification_count=None,
            )
        for detection in raw_detections:
            if not isinstance(detection, dict):
                raise InferenceServiceError("YOLO worker returned an invalid detection.")
            box = detection.get("bbox")
            clipped = clip_bbox(box, width, height)
            if clipped is None:
                continue
            try:
                class_id = int(detection["class_id"])
                class_name = str(detection["class_name"])
                confidence = float(detection["confidence"])
            except (KeyError, TypeError, ValueError) as exc:
                raise InferenceServiceError("YOLO detection metadata is invalid.") from exc
            if (
                class_id < 0
                or not math.isfinite(confidence)
                or not 0.0 <= confidence <= 1.0
            ):
                continue
            x1, y1, x2, y2 = clipped
            crop = request.frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            valid_yolo_at = time.monotonic()
            tensor = preprocess_crop(crop)[0]
            pending.append(
                (
                    tuple(float(value) for value in box),
                    class_id,
                    class_name,
                    confidence,
                    tensor,
                    valid_yolo_at,
                )
            )
        with self._state_lock:
            if request.generation != self._generation:
                return None
            self._diagnostics["last_valid_crop_count"] = len(pending)

        classified: list[ClassifiedDetection] = []
        if pending:
            tensor_payload = [
                base64.b64encode(
                    np.ascontiguousarray(item[4], dtype=np.float32).tobytes()
                ).decode("ascii")
                for item in pending
            ]
            before_get_client = time.perf_counter()
            cnn_client = self._get_client("cnn")
            cnn_startup_seconds = time.perf_counter() - before_get_client
            if self._is_stale(request.generation):
                return None
            cnn_started = time.perf_counter()
            try:
                cnn_response = cnn_client.request(
                    {
                        "session_id": request.session_id,
                        "frame_id": request.frame_id,
                        "timestamp_ms": request.timestamp_ms,
                        "tensors": tensor_payload,
                    }
                )
            except Exception as exc:
                self._set_worker_error("cnn", str(exc))
                raise
            self._validate_frame_identity(cnn_response, request)
            stage_ms["cnn_predict"] = float(cnn_response.get("predict_ms", 0))
            stage_ms["cnn_ipc"] = max(
                0, (time.perf_counter() - cnn_started) * 1000 - stage_ms["cnn_predict"]
            )
            classifications = cnn_response.get("classifications")
            if not isinstance(classifications, list) or len(classifications) != len(pending):
                raise InferenceServiceError(
                    "CNN worker returned a mismatched classification count."
                )
            for index, (item, prediction) in enumerate(zip(pending, classifications)):
                if not isinstance(prediction, dict):
                    raise InferenceServiceError("CNN worker returned invalid class data.")
                try:
                    prediction_index = int(prediction["detection_index"])
                    cnn_class_id = int(prediction["class_id"])
                    cnn_class_name = str(prediction["class_name"])
                    score = float(prediction["score"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise InferenceServiceError("CNN prediction metadata is invalid.") from exc
                if prediction_index != index:
                    raise InferenceServiceError(
                        "CNN classifications do not match detection order."
                    )
                if (
                    cnn_class_id not in self._mapping
                    or cnn_class_name != self._mapping[cnn_class_id]
                    or not math.isfinite(score)
                    or not 0.0 <= score <= 1.0
                ):
                    raise InferenceServiceError(
                        "CNN returned a class or score outside the project mapping."
                    )
                bbox, yolo_class_id, yolo_class_name, yolo_confidence, tensor, valid_yolo_at = item
                valid_cnn_at = time.monotonic()
                classified.append(
                    ClassifiedDetection(
                        bbox=bbox,
                        yolo_class_id=yolo_class_id,
                        yolo_class_name=yolo_class_name,
                        yolo_confidence=yolo_confidence,
                        cnn_class_id=cnn_class_id,
                        cnn_class_name=cnn_class_name,
                        cnn_score=score,
                        valid_yolo_at=valid_yolo_at,
                        valid_cnn_at=valid_cnn_at,
                        speech_veto=speech_veto(tensor, cnn_class_id),
                    )
                )
        with self._state_lock:
            if request.generation != self._generation:
                return None
            self._diagnostics["last_cnn_classification_count"] = len(classified)

        completed_monotonic = time.perf_counter()
        elapsed_ms = (completed_monotonic - inference_started - cnn_startup_seconds) * 1000
        self._log_pipeline_summary(
            request,
            yolo_detection_count=len(raw_detections),
            valid_crop_count=len(pending),
            classification_count=len(classified),
            elapsed_ms=elapsed_ms,
        )
        return InferenceResult(
            session_id=request.session_id,
            frame_id=request.frame_id,
            timestamp_ms=request.timestamp_ms,
            submitted_monotonic=request.submitted_monotonic,
            completed_monotonic=completed_monotonic,
            elapsed_ms=elapsed_ms,
            detections=tuple(classified),
            stage_ms=stage_ms,
        )

    @staticmethod
    def _validate_frame_identity(
        response: dict[str, object], request: _FrameRequest
    ) -> None:
        try:
            session_id = int(response["session_id"])
            frame_id = int(response["frame_id"])
            timestamp_ms = float(response["timestamp_ms"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InferenceServiceError("Inference response has no frame identity.") from exc
        if (
            session_id != request.session_id
            or frame_id != request.frame_id
            or not math.isclose(
                timestamp_ms, request.timestamp_ms, rel_tol=0.0, abs_tol=0.001
            )
        ):
            raise InferenceServiceError("Inference response belongs to a different frame.")

    def _is_stale(self, generation: int) -> bool:
        with self._state_lock:
            return generation != self._generation

    def _set_worker_error(self, worker_name: str, error: str) -> None:
        with self._state_lock:
            if self._closed.is_set():
                return
            status = self._worker_status[worker_name]
            status.update(state="error", error=error)
            self._status = f"AI Error: {worker_name.upper()} worker: {error}"
        logger.error("%s worker error: %s", worker_name.upper(), error)

    def _log_pipeline_summary(
        self,
        request: _FrameRequest,
        yolo_detection_count: int,
        valid_crop_count: int,
        classification_count: int,
        elapsed_ms: float,
    ) -> None:
        now = time.perf_counter()
        with self._state_lock:
            if now - self._last_pipeline_log_at < 5.0:
                return
            self._last_pipeline_log_at = now
        logger.debug(
            "AI pipeline session=%s frame=%s timestamp_ms=%.1f "
            "yolo_detections=%s valid_crops=%s cnn_classifications=%s "
            "result_queue=%s latency_ms=%.1f",
            request.session_id,
            request.frame_id,
            request.timestamp_ms,
            yolo_detection_count,
            valid_crop_count,
            classification_count,
            self._results.qsize(),
            elapsed_ms,
        )

    @staticmethod
    def _drain(target: queue.Queue[object]) -> None:
        while True:
            try:
                target.get_nowait()
            except queue.Empty:
                return

    @staticmethod
    def _replace_latest(target: queue.Queue[object], value: object) -> None:
        while True:
            try:
                target.put_nowait(value)
                return
            except queue.Full:
                try:
                    target.get_nowait()
                except queue.Empty:
                    continue
