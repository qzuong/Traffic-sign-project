"""Replay Step H observations at their recorded presentation times against both policies."""
import json
from pathlib import Path
import statistics
import subprocess
import sys
import threading
from types import ModuleType
from unittest.mock import patch
import wave

import cv2
import numpy as np

from src.traffic_sign_demo.desktop_ui import DesktopVideoPlayer
from src.traffic_sign_demo.speech_evidence import speech_veto
from src.traffic_sign_demo.tracked_voice_alerts import TrackedVoiceAlerts
from src.traffic_sign_demo.vision import ClassifiedDetection, DisplayFrame, clip_bbox, preprocess_crop
from src.traffic_sign_demo.voice_alerts import _clip_timing

OUT = Path(__file__).resolve().parent
BASE = OUT.parent / "step_h"

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def baseline_class():
    path = "src/traffic_sign_demo/tracked_voice_alerts.py"
    source = subprocess.check_output(["git", "show", f"57b793b:{path}"]).decode()
    module = ModuleType("src.traffic_sign_demo.step_h_voice")
    sys.modules[module.__name__] = module
    exec(compile(source, path, "exec"), module.__dict__)
    return module.TrackedVoiceAlerts

class RecordedClock:
    def __init__(self, controller, frames):
        self.controller = controller
        self.frames = iter(frames)
        self.next_frame = next(self.frames, None)
        self.now = self.next_frame[0]
        self.ended = False

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def notify(self): pass

    def wait(self, timeout=None):
        deadline = float("inf") if timeout is None else self.now + max(timeout, 1e-8)
        if self.next_frame is not None and self.next_frame[0] <= deadline:
            self.now, frame, detections = self.next_frame
            self.next_frame = next(self.frames, None)
            self.controller.observe(frame, detections)
        elif not self.ended and self.next_frame is None:
            self.ended = True
            self.controller.complete()
        elif timeout is None:
            self.controller._closed = True
        else:
            self.now = deadline

    def wait_for(self, condition, timeout=None):
        deadline = float("inf") if timeout is None else self.now + timeout
        while not condition() and self.now < deadline:
            self.wait(None if timeout is None else deadline - self.now)
        return condition()

def recording(log):
    cap = cv2.VideoCapture(log["video"])
    shape = None
    positive = {row["frame"]: row["detections"] for row in log["observations"]}
    # Preserve the actual order of displayed frames including positive late redraws.
    sample_times = [(n, at, False) for n, at in log["views"]]
    sample_times += [(n, at, True) for n, at, *_ in log["overlays"]]
    for n, at, has_result in sorted(sample_times, key=lambda row: row[1]):
        raw = positive.get(n, ()) if has_result else ()
        if raw or shape is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, n)
            ok, frame = cap.read()
            assert ok and round(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1 == n, n
            image = DesktopVideoPlayer._resize_for_display(frame)
            sh, sw = frame.shape[:2]
            shape = image.shape
        else:
            image = np.broadcast_to(np.zeros((1, 1, 3), dtype=np.uint8), shape)
        detections = []
        for item in raw:
            x, y, r, b = clip_bbox(item["bbox"], sw, sh)
            rgb = preprocess_crop(frame[y:b, x:r])[0]
            detections.append(ClassifiedDetection(**dict(item,
                speech_veto=speech_veto(rgb, item["cnn_class_id"]))))
        yield at, DisplayFrame(1, n, n * 1000 / 30, sw, sh, image), tuple(detections)
    cap.release()

def simulate(cls, frames, times):
    with patch.object(threading.Thread, "start"):
        alerts = cls(play=times.__getitem__, stop=lambda: None, clock=lambda: clock.now)
    clock = RecordedClock(alerts, frames)
    alerts._condition = clock
    alerts._run()
    return dict(stats=alerts.diagnostics, trace=alerts.trace)

def main():
    old = baseline_class()
    timings = {}
    for k in range(43):
        with wave.open(f"assets/voice_google/{k:02}.wav","rb") as clip:
            timings[k] = _clip_timing(clip, check_tail=True)
    outcomes = {}
    for filename in ("performance-live.json", "motorway-live.json", "blue-panel-initial.json"):
        log = read((OUT if filename == "blue-panel-initial.json" else BASE) / filename)
        frames = list(recording(log))
        outcomes[filename] = {
            "baseline": simulate(old, frames, timings),
            "guarded": simulate(TrackedVoiceAlerts, frames, timings),
        }
        for run, values in outcomes[filename].items():
            stats = values["stats"]
            print(filename, run, stats["played_tracks"], "suppressed",
                  stats.get("tracks_with_speech_suppression", 0), "latency med/max",
                  (statistics.median(stats["speech_latency_ms"]), max(stats["speech_latency_ms"]))
                  if stats["speech_latency_ms"] else None)
    (OUT / "matched-replay.json").write_text(json.dumps(outcomes, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()

