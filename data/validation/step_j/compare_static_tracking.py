from collections import Counter
from pathlib import Path
import json
import cv2
from evaluate_gtsrb import load_baseline_tracker
from sample_gtsdb import CACHE
from src.traffic_sign_demo.alert_tracking import AlertTracks
from src.traffic_sign_demo.vision import ClassifiedDetection,DisplayFrame,clip_bbox
a=Path(__file__).resolve().parent
rows=json.loads((a/"gtsdb-results.json").read_text(encoding="utf8"))["rows"]
old_cls=load_baseline_tracker()
counts=Counter()
for row in rows:
 n=row["frame"]; img=cv2.imread(str(CACHE/f"{n:05}.ppm")); h,w=img.shape[:2]
 dets=tuple(ClassifiedDetection(**r) for r in row["predictions"])
 old,new=old_cls(),AlertTracks()
 histories={}
 for i,ms in enumerate((0,200,400)):
    frame=DisplayFrame(n,i,ms,w,h,img)
    snapshot=lambda t:[(r.id,r.box,r.confirmed) for r in t.update(frame,dets,ms/1000)]
    before,after=snapshot(old),snapshot(new)
    assert before==after
    for tid,bbox,_ in after:
        histories.setdefault(bbox,[]).append(tid)
 for p in row["matches"]:
    box=clip_bbox(dets[int(p)].bbox,w,h)
    ids=histories[box]
    counts["matched_signs"]+=1
    counts["stable_ids"]+=len(ids)==3 and len(set(ids))==1
    counts["id_switches"]+=sum(x!=y for x,y in zip(ids,ids[1:]))
out=dict(measurement="repeated static scenes; no motion robustness inference",**counts)
(a/"matched-static-tracking.json").write_text(json.dumps(out,indent=2),encoding="utf8")
print(out)
