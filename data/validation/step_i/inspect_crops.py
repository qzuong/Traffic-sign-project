"""Recompute CNN probabilities on the immutable Step H crops with the production preprocessor."""
import json, os, sys
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf

from src.traffic_sign_demo.class_mapping import load_class_mapping
from src.traffic_sign_demo.vision import clip_bbox, preprocess_crop
from src.traffic_sign_demo.desktop_ui import DesktopVideoPlayer
from scripts.benchmark_detectors import iou

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "step_h"
CROPS = ROOT / "crops"
CROPS.mkdir(exist_ok=True)
def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

class Reader:
    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise ValueError(path)
        self.frames = {}
    def get(self, frame_id):
        if frame_id not in self.frames:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ok, data = self.cap.read()
            if not ok or round(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1 != frame_id:
                raise ValueError((self.path, frame_id))
            self.frames[frame_id] = data
        return self.frames[frame_id]

model = tf.keras.models.load_model("models/model.h5", compile=False)
mapping = load_class_mapping("models/model.py")
video = Reader(Path("data/videos/test_video.mp4"))
source = []
records = []
def append(frame, detection, tag, frame_id, **extra):
    xyxy = clip_bbox(detection["bbox"], frame.shape[1], frame.shape[0])
    x, y, r, b = xyxy
    crop = frame[y:b, x:r]
    source.append(crop)
    records.append(dict(tag=tag, frame_id=frame_id, clipped_box=xyxy, detected_box=detection["bbox"],
                        recorded_prediction_id=detection["cnn_class_id"], recorded_top1=detection["cnn_score"],
                        timestamp_ms=frame_id * 1000 / 30, **extra))

for key, row in read(BASE / "detections.json").items():
    for match in row["matches"]:
        gt, pred = row["references"][match["reference"]], row["predictions"][match["prediction"]]
        append(video.get(int(key)), pred, "annotated", int(key), ground_truth_id=gt["class_id"],
               ground_truth_box=gt["box"], iou=match["iou"])

runs = {
    "city": ("city-live.json", 0, {17: 12, 32: None}),
    "repeat": ("performance-live.json", 0, {22: 12}),
    "motorway": ("motorway-live.json", 8640, {2: 7}),
}
for name, (filename, offset, investigation) in runs.items():
    raw = read(BASE / filename)
    reader = video if offset == 0 else Reader(Path(raw["video"]))
    for row in raw["observations"]:
        n = row["frame"]
        frame = reader.get(n)
        height, width = frame.shape[:2]
        dw, dh = DesktopVideoPlayer._resize_for_display(frame).shape[1::-1]
        scale = (width / dw, height / dh) * 2
        unused = set(range(len(row["detections"])))
        for tid, box, label in row["tracks"]:
            approx = [p * s for p, s in zip(box, scale)]
            index = max(unused, key=lambda i: iou(approx, row["detections"][i]["bbox"]))
            assert iou(approx, row["detections"][index]["bbox"]) >= 0.55, (name, n, tid, box)
            unused.remove(index)
            pred = row["detections"][index]
            append(frame, pred, name, n, track_id=tid, aggregate=label, source_frame=n+offset,
                   ground_truth_id=investigation.get(tid), examined_track=tid in investigation,
                   first_yolo_at=pred["valid_yolo_at"], first_cnn_at=pred["valid_cnn_at"])

batch = np.concatenate([preprocess_crop(image) for image in source])
scores = model(batch, training=False).numpy()
for i, (image, row, vector) in enumerate(zip(source, records, scores)):
    top = np.argsort(vector)[-5:][::-1]
    row["top5"] = [dict(class_id=int(k), label=mapping[int(k)], probability=float(vector[k])) for k in top]
    if row["tag"] == "annotated" or row.get("examined_track"):
        name = f'{row["tag"]}-{row["frame_id"]}-{i}.png'
        cv2.imwrite(str(CROPS / name), image)
        row["crop"] = "crops/" + name
    row["reproduced_prediction"] = int(top[0]) == row["recorded_prediction_id"]
(ROOT / "cnn-forensics.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
print(len(records), "crops; original top-1 reproduced", sum(row["reproduced_prediction"] for row in records))
for row in records:
    if ("ground_truth_id" in row and row["ground_truth_id"] is not None
            and row["ground_truth_id"] != row["recorded_prediction_id"]):
        print(row["tag"], row["frame_id"], row.get("track_id"), row["ground_truth_id"], row["crop"],
              [(v["class_id"], round(v["probability"],5)) for v in row["top5"]])
