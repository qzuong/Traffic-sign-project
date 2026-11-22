"""Evaluate fixed, class-stratified local GTSRB test images with the demo models."""
from collections import Counter, defaultdict
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType

import cv2

from scripts.benchmark_detectors import iou
from src.traffic_sign_demo.alert_tracking import AlertTracks
from src.traffic_sign_demo.inference_service import InferenceService
from src.traffic_sign_demo.vision import DisplayFrame

HERE = Path(__file__).resolve().parent
DATA = Path(r"D:\CODE\Traffic_sign_classification\Data")
SEED = "step-j-local-gtsrb-test-v1"
PRIORITY = set(range(9)) | {9, 12, 13, 14, 15, 16, 17, 38, 40}
def load_baseline_tracker():
    path = "src/traffic_sign_demo/alert_tracking.py"
    source = subprocess.check_output(["git", "show", f"step-h-baseline:{path}"]).decode()
    module = ModuleType("src.traffic_sign_demo.step_h_track_probe")
    sys.modules[module.__name__] = module
    exec(compile(source, path, "exec"), module.__dict__)
    return module.AlertTracks

def cases():
    by_class = defaultdict(list)
    with (DATA/"Test.csv").open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            by_class[int(row["ClassId"])].append(row)
    for label in sorted(by_class):
        items = sorted(by_class[label], key=lambda row: hashlib.sha256(
            (SEED+row["Path"]).encode()).hexdigest())
        yield from items[:(12 if label in PRIORITY else 6)]

def eligible(cls, image, detections, guarded):
    tracker=cls()
    active=[]
    h,w=image.shape[:2]
    for n in (0,1):
        frame=DisplayFrame(1,n,200*n,w,h,image)
        active=tracker.update(frame,detections,1+.2*n)
    return [dict(track_id=t.id, box=t.box,
                 class_id=t.confirmed, speech_block=t.speech_block if guarded else None)
            for t in active if t.confirmed is not None]

def evaluate():
    service=InferenceService(image_size=640,confidence=.25,preload_workers=True,detector="gtsdb")
    output=[]
    old=load_baseline_tracker()
    try:
        for n,row in enumerate(cases()):
            path=DATA/row["Path"]
            img=cv2.imread(str(path))
            assert img is not None and img.shape[:2]==(int(row["Height"]),int(row["Width"]))
            ref=[int(row[f"Roi.{axis}"])+(1 if axis.endswith("2") else 0)
                 for axis in ("X1","Y1","X2","Y2")]
            service.submit(img,n,n*1000/30)
            deadline=time.monotonic()+125
            while (result:=service.poll_result()) is None:
                if time.monotonic()>deadline or service.status.startswith("AI Error:"):
                    raise RuntimeError(service.status)
                time.sleep(.01)
            assert result.frame_id==n and service.diagnostics["last_yolo_detection_count"]==len(result.detections)
            pairs=sorted(((iou(ref,d.bbox),i) for i,d in enumerate(result.detections)),reverse=True)
            best=pairs[0][1] if pairs and pairs[0][0]>=.5 else None
            H=eligible(old,img,result.detections,False)
            I=eligible(AlertTracks,img,result.detections,True)
            assert [(x["track_id"],x["box"],x["class_id"]) for x in H]==[(x["track_id"],x["box"],x["class_id"]) for x in I]
            output.append(dict(path=row["Path"], sha256=hashlib.sha256(path.read_bytes()).hexdigest(), ref_box=ref, actual_class=int(row["ClassId"]),
                predictions=[asdict(x) for x in result.detections],matched_prediction=best,
                iou=pairs[0][0] if best is not None else None,baseline=H,candidate=I))
            if n%30==0: print(n,flush=True)
    finally: service.close()
    text=dict(seed=SEED, split=str(DATA/"Test.csv"), rows=output)
    (HERE/"gtsrb-results.json").write_text(json.dumps(text,indent=2),encoding="utf-8")

if __name__=="__main__":
    evaluate()
