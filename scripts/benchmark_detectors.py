"""Run a CPU localization benchmark against manually annotated video frames."""

import argparse
import json
import os
from pathlib import Path
import statistics
import time

import cv2


def iou(a, b):
    width = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    height = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = width * height
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0


def small(box):
    return min(box[2] - box[0], box[3] - box[1]) < 32


def score(frames, annotations, threshold):
    matches = []
    missed = []
    false_positives = []
    for frame, detections in frames.items():
        expected = annotations[frame]
        pairs = sorted(
            (
                (iou(detection["box"], box), prediction_id, sign_id)
                for prediction_id, detection in enumerate(detections)
                for sign_id, (_, box) in enumerate(expected)
            ),
            reverse=True,
        )
        used_predictions, used_signs = set(), set()
        for overlap, prediction_id, sign_id in pairs:
            if overlap < threshold:
                break
            if prediction_id in used_predictions or sign_id in used_signs:
                continue
            used_predictions.add(prediction_id)
            used_signs.add(sign_id)
            label, box = expected[sign_id]
            matches.append({
                "frame": frame, "label": label, "annotation": box, "iou": overlap,
                "prediction": detections[prediction_id], "small": small(box),
            })
        missed.extend(
            {"frame": frame, "label": label, "box": box} for i, (label, box) in enumerate(expected)
            if i not in used_signs
        )
        false_positives.extend(
            {"frame": frame, **detection} for i, detection in enumerate(detections)
            if i not in used_predictions
        )
    return {
        "localized": len(matches), "missed": len(missed),
        "unmatched_predictions": len(false_positives),
        "small_localized": sum(m["small"] for m in matches),
        "median_iou": statistics.median(m["iou"] for m in matches) if matches else None,
        "matches": matches, "missed_signs": missed, "false_positives": false_positives,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("annotations", type=Path, help="JSON annotations with source PNGs beside it")
    parser.add_argument("original", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    for path in (args.original, args.candidate):
        if not path.is_file():
            parser.error(f"Required local checkpoint is missing: {path}")

    os.environ["ULTRALYTICS_SAFE_LOAD"] = "1"
    os.environ["TORCH_FORCE_WEIGHTS_ONLY_LOAD"] = "1"
    import torch
    from ultralytics import YOLO, __version__

    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    frames = {}
    for key in sorted(annotations, key=int):
        frame = cv2.imread(str(args.annotations.with_name(f"{key}.png")))
        if frame is None:
            raise ValueError(f"Missing input PNG for frame {key}")
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise ValueError(f"Could not prepare frame {key}")
        frames[key] = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)

    models = {"original": YOLO(str(args.original)), "candidate": YOLO(str(args.candidate))}
    if list(models["candidate"].names.values()) != ["traffic_sign"]:
        raise ValueError("The candidate did not expose one traffic_sign class.")
    output = {
        "torch": str(torch.__version__), "ultralytics": __version__, "cpu_threads": 2,
        "confidence": 0.25, "frame_ids": list(frames), "results": {},
    }
    for size in (320, 416, 640):
        predict = {"imgsz": size, "conf": 0.25, "device": "cpu", "verbose": False}
        for model in models.values():
            model.predict(next(iter(frames.values())), **predict)
        timings = {key: [] for key in models}
        predictions = {key: {} for key in models}
        for index, (frame_id, frame) in enumerate(frames.items()):
            for key in list(models)[::(1 if index % 2 == 0 else -1)]:
                start = time.perf_counter()
                result = models[key].predict(frame, **predict)[0]
                timings[key].append((time.perf_counter() - start) * 1000)
                predictions[key][frame_id] = [
                    {"box": box, "class": result.names[int(label)], "confidence": confidence}
                    for box, label, confidence in zip(
                        result.boxes.xyxy.tolist(), result.boxes.cls.tolist(),
                        result.boxes.conf.tolist(),
                    )
                ]
        for key in models:
            entry = {
                "median_inference_ms": statistics.median(timings[key]),
                "inference_ms": dict(zip(frames, timings[key])),
                "predictions": predictions[key],
                "iou_0.35": score(predictions[key], annotations, 0.35),
                "iou_0.50": score(predictions[key], annotations, 0.50),
            }
            output["results"][f"{key}-{size}"] = entry
            summary = entry["iou_0.50"]
            print(key, size, round(entry["median_inference_ms"], 1),
                  *(summary[name] for name in ("localized", "missed", "unmatched_predictions",
                                                "small_localized", "median_iou")), flush=True)
        args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
