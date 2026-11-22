from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import cv2
import numpy as np


def _write_message(message: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--imgsz", type=int, default=320)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--verified-sha256")
    args = parser.parse_args()
    print(f"YOLO worker sys.executable: {sys.executable}", file=sys.stderr, flush=True)

    try:
        model_path = Path(args.model)
        if not model_path.is_file():
            raise FileNotFoundError(f"Local YOLO checkpoint is missing: {model_path}")
        if args.verified_sha256:
            if hashlib.sha256(model_path.read_bytes()).hexdigest() != args.verified_sha256:
                raise ValueError("Candidate checkpoint does not match the approved SHA-256.")
            os.environ["ULTRALYTICS_SAFE_LOAD"] = "1"
            os.environ["TORCH_FORCE_WEIGHTS_ONLY_LOAD"] = "1"
        with contextlib.redirect_stdout(sys.stderr):
            import torch
            from ultralytics import YOLO

            # Leave CPU capacity for decoding, Tk and the separate CNN process.
            torch.set_num_threads(2)
            cv2.setNumThreads(1)
            model = YOLO(args.model)
            if model.task != "detect":
                raise RuntimeError(f"Expected a detection model, got {model.task!r}.")
            if args.verified_sha256 and list(model.names.values()) != ["traffic_sign"]:
                raise RuntimeError("Expected the approved single-class traffic_sign detector.")

            # Initialize the predictor and CPU kernels before accepting video frames.
            model.predict(
                source=np.zeros((360, 640, 3), dtype=np.uint8),
                imgsz=args.imgsz,
                device="cpu",
                conf=args.conf,
                verbose=False,
            )
    except Exception as exc:
        _write_message({"type": "error", "error": f"{type(exc).__name__}: {exc}"})
        return

    _write_message(
        {
            "type": "ready",
            "python": sys.executable,
            "task": model.task,
            "classes": len(model.names),
            "imgsz": args.imgsz,
        }
    )

    for line in sys.stdin:
        request = json.loads(line)
        if request.get("operation") == "stop":
            break
        try:
            decode_started = time.perf_counter()
            encoded = base64.b64decode(request["frame_jpeg"], validate=True)
            frame = cv2.imdecode(
                np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR
            )
            if frame is None or frame.size == 0:
                raise ValueError("The submitted frame could not be decoded.")
            predict_started = time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                result = model.predict(
                    source=frame,
                    imgsz=args.imgsz,
                    device="cpu",
                    conf=args.conf,
                    verbose=False,
                )[0]
            predict_finished = time.perf_counter()

            detections: list[dict[str, object]] = []
            if result.boxes is not None:
                for bbox, class_id, confidence in zip(
                    result.boxes.xyxy.cpu().tolist(),
                    result.boxes.cls.cpu().tolist(),
                    result.boxes.conf.cpu().tolist(),
                ):
                    class_id = int(class_id)
                    detections.append(
                        {
                            "bbox": [float(value) for value in bbox],
                            "class_id": class_id,
                            "class_name": str(model.names[class_id]),
                            "confidence": float(confidence),
                        }
                    )
            response = {
                "type": "result",
                "session_id": request["session_id"],
                "frame_id": request["frame_id"],
                "timestamp_ms": request["timestamp_ms"],
                "detections": detections,
                "decode_ms": (predict_started - decode_started) * 1000,
                "predict_ms": (predict_finished - predict_started) * 1000,
            }
        except Exception as exc:
            response = {
                "type": "error",
                "session_id": request.get("session_id"),
                "frame_id": request.get("frame_id"),
                "error": f"{type(exc).__name__}: {exc}",
            }
        _write_message(response)


if __name__ == "__main__":
    main()
