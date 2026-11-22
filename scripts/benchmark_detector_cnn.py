"""Classify audited detector crops using the application's CNN worker."""

import argparse
import base64
import json
from pathlib import Path
import sys

import cv2
import numpy as np

from src.traffic_sign_demo.inference_service import _JsonLineWorker
from src.traffic_sign_demo.vision import clip_bbox, preprocess_crop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    frames = {}
    for key in comparison["frame_ids"]:
        frames[key] = cv2.imread(str(args.comparison.with_name(f"{key}.png")))
        if frames[key] is None:
            raise ValueError(f"Missing source PNG for frame {key}")

    client = _JsonLineWorker(
        "cnn",
        [sys.executable, "-m", "src.traffic_sign_demo.cnn_worker",
         "--model", str(root / "models/model.h5"), "--mapping", str(root / "models/model.py")],
        root, startup_timeout=120, response_timeout=30,
    )
    try:
        output = {}
        for scenario, entry in comparison["results"].items():
            matches = {
                (match["frame"], tuple(match["prediction"]["box"])): match["label"]
                for match in entry["iou_0.50"]["matches"]
            }
            rows, tensors = [], []
            for key, predictions in entry["predictions"].items():
                frame = frames[key]
                height, width = frame.shape[:2]
                for prediction in predictions:
                    box = clip_bbox(prediction["box"], width, height)
                    if box is None:
                        continue
                    x1, y1, x2, y2 = box
                    crop = preprocess_crop(frame[y1:y2, x1:x2])
                    tensors.append(base64.b64encode(np.ascontiguousarray(crop).tobytes()).decode("ascii"))
                    rows.append({
                        "frame": int(key), **prediction,
                        "annotation": matches.get((key, tuple(prediction["box"]))),
                    })
            if tensors:
                response = client.request({
                    "session_id": 0, "frame_id": 0, "timestamp_ms": 0, "tensors": tensors,
                })
                predictions = response["classifications"]
                if len(predictions) != len(rows):
                    raise RuntimeError("CNN returned a mismatched crop count.")
                for index, (row, classification) in enumerate(zip(rows, predictions)):
                    if classification["detection_index"] != index:
                        raise RuntimeError("CNN returned crops out of order.")
                    row["cnn_label"] = classification["class_name"]
                    row["cnn_score"] = classification["score"]
            output[scenario] = rows
            print(scenario, [(row["frame"], row["annotation"], row["cnn_label"]) for row in rows], flush=True)
        args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    finally:
        client.terminate()


if __name__ == "__main__":
    main()
